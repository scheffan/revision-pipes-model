/**
 * Carga de modelos ONNX en el navegador.
 *
 * Los modelos se bajan una sola vez y quedan guardados en el navegador (Cache API): la segunda
 * visita abre al instante y funciona sin conexión. La imagen del usuario nunca sale de su compu.
 */
import * as ort from "onnxruntime-web";

export type ModelName = "radiografias" | "cordones" | "portero";

export interface DetectorConfig {
  labels: string[];
  umbral: number;
  umbral_alto?: number;
  img_size: number;
  ventanas: { overlap: number; min_ratio: number };
}

export interface PorteroConfig {
  labels: string[];
  img_size: number;
  umbral_no_seguro: number;
}

export interface LoadedModel<C> {
  session: ort.InferenceSession;
  config: C;
}

const BASE = `${import.meta.env.BASE_URL}models/`;
const CACHE = "modelos-v1";

// Sin aislamiento entre orígenes (GitHub Pages no lo permite) ONNX Runtime usa un solo hilo.
// El motor (wasm) lo empaqueta Vite junto con la app.
ort.env.wasm.numThreads = 1;

async function cachedFetch(url: string, onProgress?: (fraction: number) => void): Promise<ArrayBuffer> {
  const cache = "caches" in self ? await caches.open(CACHE).catch(() => null) : null;
  const hit = cache ? await cache.match(url) : undefined;
  if (hit) {
    onProgress?.(1);
    return hit.arrayBuffer();
  }
  const response = await fetch(url);
  if (!response.ok || !response.body) throw new Error(`No pude bajar ${url} (${response.status}).`);
  const total = Number(response.headers.get("content-length")) || 0;
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let received = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    received += value.length;
    if (total) onProgress?.(received / total);
  }
  const bytes = new Uint8Array(received);
  let offset = 0;
  for (const c of chunks) {
    bytes.set(c, offset);
    offset += c.length;
  }
  await cache?.put(url, new Response(bytes.slice())).catch(() => undefined);
  onProgress?.(1);
  return bytes.buffer;
}

const loading = new Map<ModelName, Promise<LoadedModel<unknown>>>();

/** Carga un modelo (una sola vez por sesión, aunque se pida varias veces). */
export function loadModel<C>(name: ModelName, onProgress?: (fraction: number) => void): Promise<LoadedModel<C>> {
  if (!loading.has(name)) {
    const task = (async () => {
      const config = (await (await fetch(`${BASE}modelo_${name}.json`)).json()) as C;
      const bytes = await cachedFetch(`${BASE}modelo_${name}.onnx`, onProgress);
      const session = await ort.InferenceSession.create(bytes, { executionProviders: ["wasm"] });
      return { session, config };
    })();
    task.catch(() => loading.delete(name)); // si falla, se puede reintentar
    loading.set(name, task);
  }
  return loading.get(name) as Promise<LoadedModel<C>>;
}
