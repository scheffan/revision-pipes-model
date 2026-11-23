/**
 * Guardado local en el navegador (IndexedDB): juntas, imágenes y el historial de auditoría.
 * No hay servidor: los datos y las imágenes quedan en la compu de quien usa la app.
 */
import type { Evento, Junta } from "./juntas";

const DB = "revision-soldaduras";
const VERSION = 1;

let dbPromise: Promise<IDBDatabase> | null = null;

function db(): Promise<IDBDatabase> {
  dbPromise ??= new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, VERSION);
    req.onupgradeneeded = () => {
      const d = req.result;
      d.createObjectStore("juntas", { keyPath: "id" });
      d.createObjectStore("imagenes");
      d.createObjectStore("eventos", { keyPath: "id", autoIncrement: true }).createIndex("juntaId", "juntaId");
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return dbPromise;
}

function done<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function store(name: string, mode: IDBTransactionMode = "readonly") {
  return (await db()).transaction(name, mode).objectStore(name);
}

export const nuevoId = () => crypto.randomUUID();
export const ahora = () => new Date().toISOString();

// ------------------------------------------------------------------ juntas

export async function listarJuntas(): Promise<Junta[]> {
  return done((await store("juntas")).getAll());
}

export async function leerJunta(id: string): Promise<Junta | undefined> {
  return done((await store("juntas")).get(id));
}

export async function guardarJunta(j: Junta): Promise<void> {
  await done((await store("juntas", "readwrite")).put(j));
}

/**
 * Lee, cambia y guarda una junta en una sola transacción, así dos cambios a la vez (la IA que
 * termina de analizar y el inspector que revisa) no se pisan. `fn` tiene que ser síncrona.
 */
export async function actualizarJunta(id: string, fn: (j: Junta) => Junta): Promise<Junta | undefined> {
  const tx = (await db()).transaction("juntas", "readwrite");
  const st = tx.objectStore("juntas");
  let result: Junta | undefined;
  let error: unknown = null;
  const req = st.get(id);
  req.onsuccess = () => {
    if (!req.result) return;
    try {
      result = fn(req.result as Junta);
      st.put(result);
    } catch (e) {
      error = e;
      tx.abort();
    }
  };
  await new Promise<void>((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onabort = () => (error ? resolve() : reject(tx.error));
    tx.onerror = () => undefined;
  });
  if (error) throw error;
  return result;
}

export async function borrarJunta(j: Junta): Promise<void> {
  const d = await db();
  const tx = d.transaction(["juntas", "imagenes", "eventos"], "readwrite");
  tx.objectStore("juntas").delete(j.id);
  for (const img of Object.values(j.imagenes)) if (img) tx.objectStore("imagenes").delete(img.imagenId);
  const idx = tx.objectStore("eventos").index("juntaId");
  const keys = await done(idx.getAllKeys(j.id));
  for (const k of keys) tx.objectStore("eventos").delete(k);
  await new Promise<void>((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

// ------------------------------------------------------------------ imágenes

export async function guardarImagen(blob: Blob): Promise<string> {
  const id = nuevoId();
  await done((await store("imagenes", "readwrite")).put(blob, id));
  return id;
}

export async function leerImagen(id: string): Promise<Blob | undefined> {
  return done((await store("imagenes")).get(id));
}

// ------------------------------------------------------------------ auditoría

export async function registrar(e: Omit<Evento, "id" | "fecha" | "quien"> & { quien?: string }): Promise<void> {
  const evento: Evento = { ...e, fecha: ahora(), quien: e.quien ?? (ajustes().inspector || "Sin nombre") };
  await done((await store("eventos", "readwrite")).add(evento));
}

export async function historial(juntaId: string): Promise<Evento[]> {
  const list = await done((await store("eventos")).index("juntaId").getAll(juntaId));
  return (list as Evento[]).sort((a, b) => (a.id ?? 0) - (b.id ?? 0));
}

// ------------------------------------------------------------------ ajustes

export interface Ajustes {
  inspector: string;
  norma: string;
}
export const NORMAS = ["API 1104", "ISO 5817", "ASME B31.3", "ASME IX", "Otra"];
const AJUSTES = "revision-soldaduras-ajustes";

export function ajustes(): Ajustes {
  try {
    return { inspector: "", norma: "API 1104", ...JSON.parse(localStorage.getItem(AJUSTES) ?? "{}") };
  } catch {
    return { inspector: "", norma: "API 1104" };
  }
}

export function guardarAjustes(a: Ajustes) {
  try {
    localStorage.setItem(AJUSTES, JSON.stringify(a));
  } catch {
    /* sin almacenamiento: los ajustes valen solo por esta visita */
  }
}

// ------------------------------------------------------------------ copia de seguridad

interface Copia {
  formato: "revision-soldaduras";
  version: 1;
  exportada: string;
  juntas: Junta[];
  eventos: Evento[];
  imagenes: Record<string, string>; // id → data URL
}

const aDataURL = (b: Blob) =>
  new Promise<string>((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result as string);
    r.onerror = () => reject(r.error);
    r.readAsDataURL(b);
  });

export async function exportar(): Promise<Blob> {
  const juntas = await listarJuntas();
  const eventos = (await done((await store("eventos")).getAll())) as Evento[];
  const imagenes: Record<string, string> = {};
  for (const j of juntas) {
    for (const img of Object.values(j.imagenes)) {
      const b = img && (await leerImagen(img.imagenId));
      if (img && b) imagenes[img.imagenId] = await aDataURL(b);
    }
  }
  const copia: Copia = { formato: "revision-soldaduras", version: 1, exportada: ahora(), juntas, eventos, imagenes };
  return new Blob([JSON.stringify(copia)], { type: "application/json" });
}

/** Agrega lo de la copia (si una junta ya existe con el mismo id, la reemplaza). */
export async function importar(file: File): Promise<number> {
  const copia = JSON.parse(await file.text()) as Copia;
  if (copia.formato !== "revision-soldaduras") throw new Error("Ese archivo no es una copia de esta app.");
  for (const [id, url] of Object.entries(copia.imagenes)) {
    const blob = await (await fetch(url)).blob();
    await done((await store("imagenes", "readwrite")).put(blob, id));
  }
  for (const j of copia.juntas) await guardarJunta(j);
  const ev = await store("eventos", "readwrite");
  for (const { id: _, ...e } of copia.eventos) ev.add(e);
  return copia.juntas.length;
}
