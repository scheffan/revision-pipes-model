/**
 * Juntas (soldaduras) y sus reglas: estado, riesgo para la bandeja, revisión de hallazgos y
 * decisión del inspector. Todo es lógica pura (sin pantalla ni base de datos) para poder
 * probarla con tests/juntas.test.ts.
 *
 * Principio: la IA prioriza; el inspector decide. La decisión queda bloqueada hasta que cada
 * hallazgo que no sea "sano" esté aceptado o descartado.
 */
import type { Box, Finding, Level } from "./core";

export type Slot = "radiografia" | "foto";
export const SLOTS: Slot[] = ["radiografia", "foto"];

export const TIPOS_UNION = ["Caño–caño", "Caño–codo", "Caño–T", "Caño–brida", "Reducción"] as const;
export const RESULTADOS = {
  aprobada: "Aprobada",
  reparar: "Reparar",
  rechazada: "Rechazada (cortar)",
} as const;
export type Resultado = keyof typeof RESULTADOS;

export type Revision = "pendiente" | "aceptado" | "descartado";

export interface Hallazgo {
  number: number;
  box: Box;
  level: Level;
  revision: Revision;
  /** Tipo corregido por el inspector, si lo cambió. */
  labelInspector?: string;
}

export interface Analisis {
  fecha: string;
  version: string;
  umbral: number;
  hallazgos: Hallazgo[];
}

export interface ImagenJunta {
  imagenId: string;
  nombre: string;
  analisis?: Analisis;
  error?: string;
}

export interface Decision {
  resultado: Resultado;
  nota: string;
  inspector: string;
  norma: string;
  fecha: string;
}

export interface DatosJunta {
  obra: string;
  tramo: string;
  numero: string;
  progresiva: string;
  tipoUnion: string;
  material: string;
  diametro: string;
  espesor: string;
  proceso: string;
  soldador: string;
}

export interface Junta extends DatosJunta {
  id: string;
  creada: string;
  imagenes: Partial<Record<Slot, ImagenJunta>>;
  decision?: Decision;
  ejemplo?: boolean;
}

export interface Evento {
  id?: number;
  juntaId: string;
  fecha: string;
  quien: string;
  accion: string;
  detalle: string;
}

export type Estado = "sin_analizar" | "para_revisar" | "lista" | "decidida";
export const ESTADOS: Record<Estado, string> = {
  sin_analizar: "Sin analizar",
  para_revisar: "Para revisar",
  lista: "Lista para decidir",
  decidida: "Decidida",
};

// ------------------------------------------------------------------ hallazgos

export const aHallazgos = (findings: Finding[]): Hallazgo[] =>
  findings.map((f) => ({ number: f.number, box: f.box, level: f.level, revision: "pendiente" }));

/** Los hallazgos "sanos" (cordón bueno) no hace falta revisarlos. */
export const necesitaRevision = (h: Hallazgo) => h.level !== "bien";

export const labelFinal = (h: Hallazgo) => h.labelInspector ?? h.box.label;

function imagenes(j: Junta): ImagenJunta[] {
  return SLOTS.flatMap((s) => (j.imagenes[s] ? [j.imagenes[s]!] : []));
}

function todosLosHallazgos(j: Junta): Hallazgo[] {
  return imagenes(j).flatMap((i) => i.analisis?.hallazgos ?? []);
}

export function pendientes(j: Junta): number {
  return todosLosHallazgos(j).filter((h) => necesitaRevision(h) && h.revision === "pendiente").length;
}

export function sinAnalizar(j: Junta): boolean {
  return imagenes(j).length === 0 || imagenes(j).some((i) => !i.analisis);
}

export function estado(j: Junta): Estado {
  if (j.decision) return "decidida";
  if (sinAnalizar(j)) return "sin_analizar";
  return pendientes(j) > 0 ? "para_revisar" : "lista";
}

/** Lo que dijo la IA (sin contar lo que descartó el inspector). */
export function resumenIA(j: Junta) {
  const vivos = todosLosHallazgos(j).filter((h) => h.revision !== "descartado");
  return {
    defectos: vivos.filter((h) => h.level === "defecto").length,
    revisar: vivos.filter((h) => h.level === "revisar").length,
    maxDefecto: Math.max(0, ...vivos.filter((h) => h.level === "defecto").map((h) => h.box.score ?? 0)),
    maxRevisar: Math.max(0, ...vivos.filter((h) => h.level === "revisar").map((h) => h.box.score ?? 0)),
  };
}

// ------------------------------------------------------------------ bandeja

/**
 * Grupo de riesgo (menor = más arriba en la bandeja):
 * 0 posibles defectos · 1 para revisar · 2 sin analizar · 3 sin hallazgos · 4 decididas.
 */
export function grupoRiesgo(j: Junta): number {
  if (j.decision) return 4;
  if (sinAnalizar(j)) return 2;
  const r = resumenIA(j);
  if (r.defectos) return 0;
  if (r.revisar) return 1;
  return 3;
}

/** Orden de la bandeja: por grupo de riesgo, después por confianza, después por N.º de junta. */
export function ordenarBandeja(juntas: Junta[]): Junta[] {
  const clave = (j: Junta) => {
    const r = resumenIA(j);
    return { g: grupoRiesgo(j), s: r.defectos ? r.maxDefecto : r.maxRevisar };
  };
  return juntas
    .map((j, i) => ({ j, i, k: clave(j) }))
    .sort(
      (a, b) =>
        a.k.g - b.k.g ||
        b.k.s - a.k.s ||
        a.j.numero.localeCompare(b.j.numero, "es", { numeric: true }) ||
        a.i - b.i,
    )
    .map((x) => x.j);
}

// ------------------------------------------------------------------ revisión y decisión

export type Accion = "aceptar" | "descartar" | "cambiar" | "deshacer";

/** Devuelve una copia de la junta con el hallazgo revisado y el texto para el historial. */
export function revisarHallazgo(
  j: Junta,
  slot: Slot,
  number: number,
  accion: Accion,
  nuevoLabel?: string,
): { junta: Junta; detalle: string } {
  if (j.decision) throw new Error("La junta ya está decidida: reabrila para cambiar la revisión.");
  const img = j.imagenes[slot];
  const h = img?.analisis?.hallazgos.find((x) => x.number === number);
  if (!img?.analisis || !h) throw new Error(`No existe el hallazgo ${number}.`);
  if (accion === "cambiar" && !nuevoLabel) throw new Error("Falta el tipo nuevo.");

  const nuevo: Hallazgo = { ...h };
  if (accion === "aceptar") Object.assign(nuevo, { revision: "aceptado" });
  if (accion === "descartar") Object.assign(nuevo, { revision: "descartado" });
  if (accion === "cambiar") {
    nuevo.revision = "aceptado";
    nuevo.labelInspector = nuevoLabel === h.box.label ? undefined : nuevoLabel;
  }
  if (accion === "deshacer") {
    nuevo.revision = "pendiente";
    delete nuevo.labelInspector;
  }
  const hallazgos = img.analisis.hallazgos.map((x) => (x.number === number ? nuevo : x));
  const junta: Junta = {
    ...j,
    imagenes: { ...j.imagenes, [slot]: { ...img, analisis: { ...img.analisis, hallazgos } } },
  };
  const donde = slot === "radiografia" ? "radiografía" : "foto";
  const verbo = { aceptar: "aceptó", descartar: "descartó", cambiar: "cambió", deshacer: "volvió a pendiente" }[accion];
  const extra = accion === "cambiar" ? ` (${h.box.label} → ${nuevoLabel})` : "";
  return { junta, detalle: `${verbo} el hallazgo ${number} de la ${donde}${extra}` };
}

export function puedeDecidir(j: Junta): { ok: boolean; motivo?: string } {
  if (j.decision) return { ok: false, motivo: "Ya está decidida." };
  if (sinAnalizar(j)) return { ok: false, motivo: "Falta analizar alguna imagen." };
  const n = pendientes(j);
  if (n) return { ok: false, motivo: `Faltan revisar ${n} hallazgo${n > 1 ? "s" : ""}.` };
  return { ok: true };
}

export function decidir(j: Junta, d: Decision): Junta {
  const p = puedeDecidir(j);
  if (!p.ok) throw new Error(p.motivo);
  if (!d.inspector.trim()) throw new Error("Falta el nombre del inspector.");
  if (d.resultado !== "aprobada" && !d.nota.trim()) throw new Error("Para reparar o rechazar, escribí el motivo.");
  return { ...j, decision: { ...d, nota: d.nota.trim(), inspector: d.inspector.trim() } };
}

export function reabrir(j: Junta): Junta {
  const { decision: _, ...resto } = j;
  return resto;
}

/** Defectos aceptados por el inspector (lo que va al informe como hallazgo confirmado). */
export function confirmados(j: Junta): { slot: Slot; h: Hallazgo }[] {
  return SLOTS.flatMap((slot) =>
    (j.imagenes[slot]?.analisis?.hallazgos ?? [])
      .filter((h) => necesitaRevision(h) && h.revision === "aceptado")
      .map((h) => ({ slot, h })),
  );
}

// ------------------------------------------------------------------ carga

export function validarJunta(
  d: DatosJunta,
  slots: Slot[],
  existentes: Junta[],
  idPropio?: string,
): Partial<Record<keyof DatosJunta | "imagenes", string>> {
  const e: Partial<Record<keyof DatosJunta | "imagenes", string>> = {};
  if (!d.obra.trim()) e.obra = "Indicá la obra.";
  if (!d.tramo.trim()) e.tramo = "Indicá el tramo.";
  if (!d.numero.trim()) e.numero = "Indicá el N.º de junta.";
  else if (
    existentes.some(
      (j) => j.id !== idPropio && j.obra.trim() === d.obra.trim() && j.numero.trim().toLowerCase() === d.numero.trim().toLowerCase(),
    )
  )
    e.numero = "Ya hay una junta con ese número en esta obra.";
  if (slots.length === 0) e.imagenes = "Subí la radiografía, la foto del cordón o ambas.";
  return e;
}

/** Obras y tramos ya cargados, para elegir en vez de escribir. */
export function obrasYTramos(juntas: Junta[]): Map<string, string[]> {
  const m = new Map<string, Set<string>>();
  for (const j of juntas) {
    if (!m.has(j.obra)) m.set(j.obra, new Set());
    m.get(j.obra)!.add(j.tramo);
  }
  const out = new Map<string, string[]>();
  for (const [obra, tramos] of [...m].sort((a, b) => a[0].localeCompare(b[0], "es"))) {
    out.set(obra, [...tramos].sort((a, b) => a.localeCompare(b, "es", { numeric: true })));
  }
  return out;
}
