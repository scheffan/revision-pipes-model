/**
 * Análisis de una imagen en el navegador: portero (¿qué imagen es?) y detector de defectos.
 * Misma preparación que en Python: la región se estira a un cuadrado y los píxeles van de 0 a 1.
 */
import * as ort from "onnxruntime-web";
import { decode, dropNested, merge, toPlate, windows, type Box } from "./core";
import { resizeRGB } from "./resize";
import type { DetectorConfig, LoadedModel, PorteroConfig } from "./models";

export type ImageKind = "radiografia" | "foto_cordon" | "otra";

/**
 * Región de la imagen → tensor (1, 3, size, size) con valores entre 0 y 1.
 * Se lee la región en su tamaño original y se redimensiona igual que Pillow (ver resize.ts).
 */
export function toTensor(
  source: CanvasImageSource,
  region: [number, number, number, number],
  size: number,
): ort.Tensor {
  const [x0, y0, x1, y1] = region.map(Math.round);
  const w = x1 - x0;
  const h = y1 - y0;
  const canvas = new OffscreenCanvas(w, h);
  const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
  ctx.drawImage(source, x0, y0, w, h, 0, 0, w, h); // 1:1, sin remuestrear
  const rgb = resizeRGB(ctx.getImageData(0, 0, w, h).data, w, h, size, size);
  const plane = size * size;
  const out = new Float32Array(3 * plane);
  for (let i = 0; i < plane; i++) {
    out[i] = rgb[i * 3] / 255;
    out[plane + i] = rgb[i * 3 + 1] / 255;
    out[2 * plane + i] = rgb[i * 3 + 2] / 255;
  }
  return new ort.Tensor("float32", out, [1, 3, size, size]);
}

export interface PorteroResult {
  kind: ImageKind;
  confidence: number;
  sure: boolean;
  probabilities: Record<ImageKind, number>;
}

export async function identify(
  model: LoadedModel<PorteroConfig>,
  image: CanvasImageSource & { width: number; height: number },
): Promise<PorteroResult> {
  const { session, config } = model;
  const input = toTensor(image, [0, 0, image.width, image.height], config.img_size);
  const output = await session.run({ pixel_values: input });
  const probs = output[session.outputNames[0]].data as Float32Array;
  const entries = config.labels.map((label, i) => [label, probs[i]] as [ImageKind, number]);
  const [kind, confidence] = entries.reduce((a, b) => (b[1] > a[1] ? b : a));
  return {
    kind,
    confidence,
    sure: confidence >= config.umbral_no_seguro,
    probabilities: Object.fromEntries(entries) as Record<ImageKind, number>,
  };
}

/** Detecta en toda la imagen; si es alargada, ventana por ventana, y une los duplicados. */
export async function detect(
  model: LoadedModel<DetectorConfig>,
  image: CanvasImageSource & { width: number; height: number },
  onWindow?: (done: number, total: number) => void,
): Promise<Box[]> {
  const { session, config } = model;
  const wins = windows(image.width, image.height, config.ventanas.overlap, config.ventanas.min_ratio);
  const found: Box[] = [];
  for (const [i, win] of wins.entries()) {
    const input = toTensor(image, win, config.img_size);
    const out = await session.run({ pixel_values: input });
    const logits = out[session.outputNames[0]];
    const boxes = out[session.outputNames[1]];
    const numClasses = logits.dims[logits.dims.length - 1];
    const size: [number, number] = [win[2] - win[0], win[3] - win[1]];
    found.push(
      ...toPlate(
        decode(logits.data as Float32Array, boxes.data as Float32Array, numClasses, size, config.labels, config.umbral),
        win,
      ),
    );
    onWindow?.(i + 1, wins.length);
  }
  return dropNested(merge(found));
}
