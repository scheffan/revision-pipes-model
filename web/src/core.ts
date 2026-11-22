/**
 * Lógica de detección, traducida de Python (src/revision_pipes) para correr en el navegador.
 *
 * Cada función replica a su par en Python. Los tests de tests/core.test.ts comparan contra
 * casos generados con el código Python (tests/fixtures/core_cases.json), así la app web no
 * puede dar resultados distintos sin que se note.
 */

export interface Box {
  xMin: number;
  yMin: number;
  xMax: number;
  yMax: number;
  label: string;
  score: number | null;
}

export type Window = [number, number, number, number]; // xMin, yMin, xMax, yMax

const MIN_BOX_SIDE = 1.0;

export const width = (b: Box) => b.xMax - b.xMin;
export const height = (b: Box) => b.yMax - b.yMin;
export const area = (b: Box) => Math.max(0, width(b)) * Math.max(0, height(b));

export function clip(b: Box, imageWidth: number, imageHeight: number): Box {
  const c = (v: number, max: number) => Math.min(Math.max(v, 0), max);
  return {
    ...b,
    xMin: c(b.xMin, imageWidth),
    yMin: c(b.yMin, imageHeight),
    xMax: c(b.xMax, imageWidth),
    yMax: c(b.yMax, imageHeight),
  };
}

export const isValid = (b: Box) => width(b) >= MIN_BOX_SIDE && height(b) >= MIN_BOX_SIDE;

/** Intersección sobre unión (0 a 1). */
export function iou(a: Box, b: Box): number {
  const ix = Math.max(0, Math.min(a.xMax, b.xMax) - Math.max(a.xMin, b.xMin));
  const iy = Math.max(0, Math.min(a.yMax, b.yMax) - Math.max(a.yMin, b.yMin));
  const inter = ix * iy;
  const union = area(a) + area(b) - inter;
  return union > 0 ? inter / union : 0;
}

/** Ventanas cuadradas superpuestas para placas alargadas (una sola si es casi cuadrada). */
export function windows(w: number, h: number, overlap = 0.25, minRatio = 1.5): Window[] {
  if (!(overlap >= 0 && overlap < 1)) throw new Error("La superposición debe estar entre 0 y 1.");
  const longSide = Math.max(w, h);
  const shortSide = Math.min(w, h);
  if (shortSide <= 0) throw new Error("La imagen no tiene tamaño.");
  if (longSide / shortSide < minRatio) return [[0, 0, w, h]];
  const step = Math.max(1, Math.floor(shortSide * (1 - overlap)));
  const starts = new Set<number>();
  for (let s = 0; s < longSide - shortSide; s += step) starts.add(s);
  starts.add(longSide - shortSide);
  const sorted = [...starts].sort((a, b) => a - b);
  return w >= h
    ? sorted.map((s): Window => [s, 0, s + shortSide, h])
    : sorted.map((s): Window => [0, s, w, s + shortSide]);
}

/** De coordenadas de la ventana a coordenadas de la placa. */
export function toPlate(boxes: Box[], window: Window): Box[] {
  const [x0, y0] = window;
  return boxes.map((b) => ({ ...b, xMin: b.xMin + x0, yMin: b.yMin + y0, xMax: b.xMax + x0, yMax: b.yMax + y0 }));
}

/** Une duplicados de la misma clase (ventanas que se pisan): queda el de más confianza. */
export function merge(boxes: Box[], iouThreshold = 0.5): Box[] {
  const ordered = stableSortBy(boxes, (b) => -(b.score ?? 1));
  const kept: Box[] = [];
  for (const b of ordered) {
    if (kept.every((k) => k.label !== b.label || iou(k, b) < iouThreshold)) kept.push(b);
  }
  return kept;
}

/**
 * Salida cruda de RT-DETR → recuadros en píxeles por encima del umbral.
 * logits: [consultas × clases] (sigmoide por clase); predBoxes: [consultas × 4] relativos cx, cy, w, h.
 */
export function decode(
  logits: Float32Array | number[],
  predBoxes: Float32Array | number[],
  numClasses: number,
  imageSize: [number, number],
  labels: string[],
  threshold: number,
): Box[] {
  if (numClasses !== labels.length) {
    throw new Error(`El modelo tiene ${numClasses} clases y se pasaron ${labels.length}.`);
  }
  const queries = logits.length / numClasses;
  const bestScore = new Float64Array(queries);
  const bestClass = new Int32Array(queries);
  for (let q = 0; q < queries; q++) {
    let best = -Infinity;
    let cls = 0;
    for (let c = 0; c < numClasses; c++) {
      const s = 1 / (1 + Math.exp(-logits[q * numClasses + c]));
      if (s > best) {
        best = s;
        cls = c;
      }
    }
    bestScore[q] = best;
    bestClass[q] = cls;
  }
  const order = stableSortBy([...Array(queries).keys()], (q) => -bestScore[q]);
  const [w, h] = imageSize;
  const out: Box[] = [];
  for (const q of order) {
    const score = bestScore[q];
    if (score < threshold) break;
    const [cx, cy, bw, bh] = [0, 1, 2, 3].map((i) => predBoxes[q * 4 + i]);
    const box = clip(
      {
        xMin: (cx - bw / 2) * w,
        yMin: (cy - bh / 2) * h,
        xMax: (cx + bw / 2) * w,
        yMax: (cy + bh / 2) * h,
        label: labels[bestClass[q]],
        score,
      },
      w,
      h,
    );
    out.push(box);
  }
  return out.filter(isValid);
}

// ---------------------------------------------------------------- lectura para el inspector

export type Level = "defecto" | "revisar" | "bien";

export interface Finding {
  number: number;
  box: Box;
  level: Level;
}

const GOOD_LABELS = new Set(["Good Weld"]);

function overlapSmall(a: Box, b: Box): number {
  const w = Math.max(0, Math.min(a.xMax, b.xMax) - Math.max(a.xMin, b.xMin));
  const h = Math.max(0, Math.min(a.yMax, b.yMax) - Math.max(a.yMin, b.yMin));
  return (w * h) / Math.min(Math.max(area(a), 1e-9), Math.max(area(b), 1e-9));
}

/** Quita recuadros encimados de la misma clase: queda el más seguro. */
export function dropNested(boxes: Box[], minInside = 0.8): Box[] {
  const kept: Box[] = [];
  for (const b of stableSortBy(boxes, (x) => -(x.score ?? 0))) {
    if (!kept.some((k) => k.label === b.label && overlapSmall(k, b) >= minInside)) kept.push(b);
  }
  return kept;
}

/** Nivel de cada hallazgo; primero los defectos seguros. */
export function classify(boxes: Box[], highThreshold: number): Finding[] {
  if (!(highThreshold >= 0 && highThreshold <= 1)) throw new Error("El umbral alto debe estar entre 0 y 1.");
  const level = (b: Box): Level =>
    GOOD_LABELS.has(b.label) ? "bien" : (b.score ?? 0) >= highThreshold ? "defecto" : "revisar";
  const rank: Record<Level, number> = { defecto: 0, revisar: 1, bien: 2 };
  const ranked = stableSortBy(boxes, (b) => rank[level(b)] * 10 - (b.score ?? 0));
  return ranked.map((box, i) => ({ number: i + 1, box, level: level(box) }));
}

export function verdict(findings: Finding[]): string {
  const nDef = findings.filter((f) => f.level === "defecto").length;
  const nRev = findings.filter((f) => f.level === "revisar").length;
  const s = (n: number) => (n > 1 ? "s" : "");
  if (nDef) return `${nDef} posible${s(nDef)} defecto${s(nDef)}` + (nRev ? ` y ${nRev} para revisar` : "");
  if (nRev) return `Sin defectos claros · ${nRev} zona${s(nRev)} para revisar`;
  return "Sin hallazgos";
}

/** Orden estable (igual que sorted() de Python ante empates). */
function stableSortBy<T>(items: T[], key: (x: T) => number): T[] {
  return items
    .map((item, i) => ({ item, i, k: key(item) }))
    .sort((a, b) => a.k - b.k || a.i - b.i)
    .map((x) => x.item);
}
