/**
 * Análisis de las imágenes de cada junta: modelos con barra de progreso global y una cola que
 * analiza lo pendiente (también lo que quedó a medias si se cerró la pestaña).
 */
import { classify, verdict, type Finding } from "./core";
import { detect, identify, type ImageKind, type PorteroResult } from "./analyze";
import { aHallazgos, SLOTS, type Analisis, type Slot } from "./juntas";
import { loadModel, type DetectorConfig, type ModelName, type PorteroConfig } from "./models";
import { actualizarJunta, ahora, leerImagen, leerJunta, listarJuntas, registrar } from "./store";

export const DEFAULT_HIGH = 0.5; // provisorio: solo decide rojo o amarillo, nunca oculta

export const SLOT_INFO: Record<Slot, { modelo: "radiografias" | "cordones"; kind: ImageKind; nombre: string; corto: string }> = {
  radiografia: { modelo: "radiografias", kind: "radiografia", nombre: "radiografía", corto: "RX" },
  foto: { modelo: "cordones", kind: "foto_cordon", nombre: "foto del cordón", corto: "Foto" },
};

type Progreso = (texto: string | null, fraccion?: number) => void;
let progreso: Progreso = () => undefined;
export const alProgresar = (fn: Progreso) => (progreso = fn);

const cambios = new Set<(juntaId: string) => void>();
export const alCambiar = (fn: (juntaId: string) => void) => cambios.add(fn);
const avisar = (id: string) => cambios.forEach((fn) => fn(id));

export async function modelo<C>(name: ModelName, label: string, size: string) {
  let mostrado = false;
  const m = await loadModel<C>(name, (f) => {
    if (f < 1) {
      mostrado = true;
      progreso(`Bajando ${label} (${size}). Solo la primera vez; después queda guardado.`, f);
    }
  });
  if (mostrado) progreso(null);
  return m;
}

export function abrirBitmap(blob: Blob): Promise<ImageBitmap> {
  // sin conversión de color: los píxeles tal cual vienen en el archivo, como los lee Pillow
  return createImageBitmap(blob, { colorSpaceConversion: "none", premultiplyAlpha: "none" });
}

export async function revisarTipo(image: ImageBitmap): Promise<PorteroResult> {
  const portero = await modelo<PorteroConfig>("portero", "el portero", "6 MB");
  return identify(portero, image);
}

export async function detectar(
  slot: Slot,
  image: ImageBitmap,
  onWindow?: (done: number, total: number) => void,
): Promise<{ findings: Finding[]; umbral: number; version: string }> {
  const info = SLOT_INFO[slot];
  const det = await modelo<DetectorConfig & { version?: string }>(info.modelo, `el modelo de ${info.nombre}`, "81 MB");
  const boxes = await detect(det, image, onWindow);
  const umbral = det.config.umbral_alto ?? DEFAULT_HIGH;
  return { findings: classify(boxes, umbral), umbral, version: det.config.version ?? "" };
}

// ------------------------------------------------------------------ cola

let corriendo = false;
let otraVuelta = false;

/** Analiza todas las imágenes sin análisis. Si ya está corriendo, vuelve a pasar al terminar. */
export async function analizarPendientes(): Promise<void> {
  if (corriendo) {
    otraVuelta = true;
    return;
  }
  corriendo = true;
  try {
    do {
      otraVuelta = false;
      const juntas = (await listarJuntas()).filter((j) => !j.decision);
      for (const j of juntas) {
        for (const slot of SLOTS) {
          if (j.imagenes[slot] && !j.imagenes[slot]!.analisis) await analizarUna(j.id, slot);
        }
      }
    } while (otraVuelta);
  } finally {
    corriendo = false;
    progreso(null);
  }
}

async function analizarUna(juntaId: string, slot: Slot) {
  const j = await leerJunta(juntaId);
  const img = j?.imagenes[slot];
  if (!j || !img || img.analisis) return;
  const info = SLOT_INFO[slot];
  try {
    const blob = await leerImagen(img.imagenId);
    if (!blob) throw new Error("no encuentro la imagen guardada");
    const bitmap = await abrirBitmap(blob);
    progreso(`Analizando ${info.nombre} de la junta ${j.numero}…`);
    const r = await detectar(slot, bitmap, (done, total) => {
      if (total > 1) progreso(`Analizando ${info.nombre} de la junta ${j.numero}: parte ${done} de ${total}`, done / total);
    });
    bitmap.close();
    const analisis: Analisis = { fecha: ahora(), version: r.version, umbral: r.umbral, hallazgos: aHallazgos(r.findings) };
    // la imagen pudo cambiar o borrarse mientras tanto: solo se guarda si sigue siendo la misma
    const guardada = await actualizarJunta(juntaId, (f) =>
      f.imagenes[slot]?.imagenId === img.imagenId && !f.imagenes[slot]!.analisis
        ? { ...f, imagenes: { ...f.imagenes, [slot]: { ...f.imagenes[slot]!, analisis, error: undefined } } }
        : f,
    );
    if (!guardada) return;
    await registrar({ juntaId, accion: "IA", detalle: `analizó la ${info.nombre}: ${verdict(r.findings).toLowerCase()}`, quien: "IA" });
  } catch (error) {
    await actualizarJunta(juntaId, (f) =>
      f.imagenes[slot]?.imagenId === img.imagenId
        ? { ...f, imagenes: { ...f.imagenes, [slot]: { ...f.imagenes[slot]!, error: (error as Error).message } } }
        : f,
    );
    progreso(`No pude analizar la ${info.nombre} de la junta ${j.numero}: ${(error as Error).message}`);
  } finally {
    avisar(juntaId);
  }
}
