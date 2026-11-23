/**
 * Visor tipo negatoscopio: zoom con la rueda (hacia el puntero), arrastre, brillo, contraste,
 * invertir y los hallazgos encima. Los textos se dibujan en tamaño de pantalla, así se leen
 * igual con cualquier zoom.
 */
import type { Finding } from "./core";

/** Hallazgo para dibujar; si viene de una revisión trae lo que decidió el inspector. */
export type Marca = Finding & { revision?: "pendiente" | "aceptado" | "descartado"; labelInspector?: string };
import { displayName } from "./labels";

export const COLORS = { defecto: "#dc2626", revisar: "#eab308", bien: "#16a34a", cordonMalo: "#f97316" };

export interface ViewSettings {
  brightness: number; // 1 = normal
  contrast: number; // 1 = normal
  invert: boolean;
  showGood: boolean;
}

export class Viewer {
  private ctx: CanvasRenderingContext2D;
  private image: (CanvasImageSource & { width: number; height: number }) | null = null;
  private findings: Marca[] = [];
  private scale = 1;
  private offset = { x: 0, y: 0 };
  private drag: { x: number; y: number } | null = null;
  selected: number | null = null;
  settings: ViewSettings = { brightness: 1, contrast: 1, invert: false, showGood: true };
  onSelect?: (n: number | null) => void;
  onZoom?: () => void;

  constructor(private canvas: HTMLCanvasElement) {
    this.ctx = canvas.getContext("2d")!;
    new ResizeObserver(() => this.resize()).observe(canvas);
    canvas.addEventListener("wheel", (e) => this.onWheel(e), { passive: false });
    canvas.addEventListener("pointerdown", (e) => this.onDown(e));
    canvas.addEventListener("pointermove", (e) => this.onMove(e));
    canvas.addEventListener("pointerup", (e) => this.onUp(e));
    canvas.addEventListener("dblclick", () => this.fit());
  }

  setImage(image: CanvasImageSource & { width: number; height: number }) {
    this.image = image;
    this.findings = [];
    this.selected = null;
    this.fit();
  }

  clear() {
    this.image = null;
    this.findings = [];
    this.selected = null;
    this.draw();
  }

  get hasImage() {
    return this.image !== null;
  }

  setFindings(findings: Marca[]) {
    this.findings = findings;
    this.draw();
  }

  update(settings: Partial<ViewSettings>) {
    Object.assign(this.settings, settings);
    this.draw();
  }

  /** Imagen entera a la vista. */
  fit() {
    if (!this.image) return this.draw();
    const { width, height } = this.canvas.getBoundingClientRect();
    if (!width || !height) return; // oculto: se ajusta cuando aparezca
    this.scale = Math.min(width / this.image.width, height / this.image.height) * 0.95;
    this.offset = {
      x: (width - this.image.width * this.scale) / 2,
      y: (height - this.image.height * this.scale) / 2,
    };
    this.draw();
    this.onZoom?.();
  }

  zoomBy(factor: number, cx?: number, cy?: number) {
    const rect = this.canvas.getBoundingClientRect();
    const px = cx ?? rect.width / 2;
    const py = cy ?? rect.height / 2;
    const next = Math.min(Math.max(this.scale * factor, 0.05), 40);
    const k = next / this.scale;
    this.offset = { x: px - (px - this.offset.x) * k, y: py - (py - this.offset.y) * k };
    this.scale = next;
    this.draw();
    this.onZoom?.();
  }

  /** Centra y acerca un hallazgo. */
  focus(number: number) {
    const f = this.findings.find((x) => x.number === number);
    if (!f) return;
    const rect = this.canvas.getBoundingClientRect();
    const b = f.box;
    const w = Math.max(b.xMax - b.xMin, 1);
    const h = Math.max(b.yMax - b.yMin, 1);
    this.scale = Math.min(Math.min(rect.width / w, rect.height / h) * 0.5, 40);
    this.offset = {
      x: rect.width / 2 - ((b.xMin + b.xMax) / 2) * this.scale,
      y: rect.height / 2 - ((b.yMin + b.yMax) / 2) * this.scale,
    };
    this.selected = number;
    this.draw();
  }

  get zoom() {
    return this.scale;
  }

  private resize() {
    const dpr = window.devicePixelRatio || 1;
    const { width, height } = this.canvas.getBoundingClientRect();
    this.canvas.width = Math.round(width * dpr);
    this.canvas.height = Math.round(height * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.fit();
  }

  private onWheel(e: WheelEvent) {
    e.preventDefault();
    const rect = this.canvas.getBoundingClientRect();
    this.zoomBy(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX - rect.left, e.clientY - rect.top);
  }

  private onDown(e: PointerEvent) {
    this.canvas.setPointerCapture(e.pointerId);
    this.drag = { x: e.clientX, y: e.clientY };
    this.canvas.style.cursor = "grabbing";
  }

  private onMove(e: PointerEvent) {
    if (!this.drag) return;
    this.offset.x += e.clientX - this.drag.x;
    this.offset.y += e.clientY - this.drag.y;
    this.drag = { x: e.clientX, y: e.clientY };
    this.draw();
  }

  private onUp(e: PointerEvent) {
    const moved = this.drag && Math.hypot(e.clientX - this.drag.x, e.clientY - this.drag.y) > 0;
    this.drag = null;
    this.canvas.style.cursor = "grab";
    if (moved) return;
    // Clic sin arrastrar: seleccionar el hallazgo más chico bajo el puntero
    const rect = this.canvas.getBoundingClientRect();
    const ix = (e.clientX - rect.left - this.offset.x) / this.scale;
    const iy = (e.clientY - rect.top - this.offset.y) / this.scale;
    const hit = this.visible()
      .filter((f) => ix >= f.box.xMin && ix <= f.box.xMax && iy >= f.box.yMin && iy <= f.box.yMax)
      .sort((a, b) => area(a) - area(b))[0];
    this.selected = hit ? hit.number : null;
    this.onSelect?.(this.selected);
    this.draw();
  }

  private visible() {
    return this.findings.filter((f) => this.settings.showGood || f.level !== "bien");
  }

  draw() {
    const { ctx } = this;
    const { width, height } = this.canvas.getBoundingClientRect();
    ctx.save();
    ctx.fillStyle = "#0b0f14";
    ctx.fillRect(0, 0, width, height);
    if (!this.image) {
      ctx.restore();
      return;
    }
    const s = this.settings;
    ctx.filter = `brightness(${s.brightness}) contrast(${s.contrast})${s.invert ? " invert(1)" : ""}`;
    ctx.imageSmoothingEnabled = this.scale < 3; // con mucho zoom se ven los píxeles reales
    ctx.drawImage(this.image, this.offset.x, this.offset.y, this.image.width * this.scale, this.image.height * this.scale);
    ctx.filter = "none";

    // del menos importante al más importante: el rojo queda arriba
    for (const f of [...this.visible()].reverse()) this.drawFinding(f);
    ctx.restore();
  }

  private drawFinding(f: Marca) {
    dibujarMarca(this.ctx, f, this.offset, this.scale, this.selected === f.number);
  }
}

const area = (f: Marca) => (f.box.xMax - f.box.xMin) * (f.box.yMax - f.box.yMin);

/** Dibuja un hallazgo; los textos van en tamaño de pantalla para que se lean con cualquier zoom. */
export function dibujarMarca(
  ctx: CanvasRenderingContext2D,
  f: Marca,
  offset: { x: number; y: number },
  scale: number,
  selected: boolean,
  fontPx = 12,
) {
  const b = f.box;
  const x = offset.x + b.xMin * scale;
  const y = offset.y + b.yMin * scale;
  const w = (b.xMax - b.xMin) * scale;
  const h = (b.yMax - b.yMin) * scale;
  const descartado = f.revision === "descartado";
  const label = f.labelInspector ?? b.label;
  const color = descartado
    ? "#64748b"
    : f.level === "defecto" && label === "Bad Weld"
      ? COLORS.cordonMalo
      : COLORS[f.level];
  const dashed = f.level === "revisar" || descartado;
  const k = fontPx / 12;
  ctx.lineWidth = (selected ? 3 : dashed ? 1.5 : 2) * k;
  ctx.setLineDash(dashed ? [6 * k, 4 * k] : []);
  ctx.strokeStyle = color;
  ctx.strokeRect(x, y, w, h);
  ctx.setLineDash([]);
  if (selected) {
    ctx.fillStyle = `${color}22`;
    ctx.fillRect(x, y, w, h);
  }
  if (descartado && !selected) return; // descartado: solo el contorno gris, sin etiqueta
  const mark = descartado ? "✕ " : f.revision === "aceptado" ? "✓ " : f.level === "revisar" ? "? " : "";
  const score = f.labelInspector ? "" : ` ${Math.round((b.score ?? 0) * 100)}%`;
  const tag = `${mark}${f.number} ${displayName(label)}${score}`;
  ctx.font = `600 ${fontPx}px system-ui, sans-serif`;
  const th = fontPx * 1.5;
  const tw = ctx.measureText(tag).width + 8 * k;
  const ty = y - th < 0 ? y : y - th;
  const ancho = ctx.canvas.clientWidth || ctx.canvas.width;
  const tx = Math.max(0, Math.min(x, ancho - tw)); // que la etiqueta no se salga por la derecha
  ctx.fillStyle = color;
  ctx.fillRect(tx, ty, tw, th);
  ctx.fillStyle = f.level === "revisar" && !descartado ? "#111" : "#fff";
  ctx.fillText(tag, tx + 4 * k, ty + th * 0.72);
}

/** Imagen con sus marcas en un canvas aparte (para el informe). */
export function imagenMarcada(
  image: CanvasImageSource & { width: number; height: number },
  findings: Marca[],
  maxSide = 1400,
): HTMLCanvasElement {
  const scale = Math.min(1, maxSide / Math.max(image.width, image.height)) || 1;
  const up = Math.max(1, 700 / Math.max(image.width * scale, image.height * scale)); // placas chicas: agrandar
  const s = scale * up;
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(image.width * s);
  canvas.height = Math.round(image.height * s);
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
  const font = Math.max(12, Math.round(canvas.width / 55));
  for (const f of [...findings].reverse()) dibujarMarca(ctx, f, { x: 0, y: 0 }, s, false, font);
  return canvas;
}
