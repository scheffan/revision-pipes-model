/**
 * Cargar (o editar) una soldadura: datos de la junta y sus imágenes. El portero revisa cada
 * imagen al elegirla y avisa si no coincide con el lugar donde se puso.
 */
import { obrasYTramos, SLOTS, TIPOS_UNION, validarJunta, type DatosJunta, type ImagenJunta, type Junta, type Slot } from "../juntas";
import { abrirBitmap, analizarPendientes, revisarTipo, SLOT_INFO } from "../pipeline";
import { actualizarJunta, ahora, guardarImagen, guardarJunta, leerImagen, leerJunta, listarJuntas, nuevoId, registrar } from "../store";
import { $, esc, gate, toast } from "./ui";

const CAMPOS: (keyof DatosJunta)[] = [
  "obra", "tramo", "numero", "progresiva", "tipoUnion", "material", "diametro", "espesor", "proceso", "soldador",
];

interface SlotState {
  blob: Blob | null; // imagen nueva elegida
  nombre: string;
  existente?: ImagenJunta; // imagen ya guardada (al editar)
  url?: string;
}

const form = () => $<HTMLFormElement>("form-junta");
const slots: Record<Slot, SlotState | null> = { radiografia: null, foto: null };
let editando: Junta | null = null;
let juntas: Junta[] = [];
const revisionId: Record<Slot, number> = { radiografia: 0, foto: 0 };

const slotEl = (s: Slot) => document.querySelector<HTMLElement>(`.slot[data-slot="${s}"]`)!;
const input = (name: string) => form().elements.namedItem(name) as HTMLInputElement | HTMLSelectElement;

function pintarSlot(s: Slot) {
  const el = slotEl(s);
  const st = slots[s];
  const img = el.querySelector("img")!;
  img.hidden = !st?.url;
  if (st?.url) img.src = st.url;
  el.querySelector<HTMLElement>(".slot-empty")!.hidden = !!st;
  el.querySelector<HTMLElement>(".slot-remove")!.hidden = !st;
  el.querySelector<HTMLElement>("label")!.firstChild!.textContent = st ? "Cambiar " : "Elegir ";
  el.classList.toggle("filled", !!st);
  if (!st) el.querySelector<HTMLElement>(".slot-note")!.hidden = true;
}

function nota(s: Slot, clase: string, texto: string, acciones: { label: string; main?: boolean; run: () => void }[] = []) {
  const el = slotEl(s).querySelector<HTMLElement>(".slot-note")!;
  if (acciones.length) {
    gate(el, texto, acciones, clase === "stop");
    el.classList.add("slot-note");
    return;
  }
  el.hidden = false;
  el.className = `slot-note ${clase}`;
  el.textContent = texto;
}

async function elegir(s: Slot, file: File | Blob, nombre: string) {
  const id = ++revisionId[s];
  let bitmap: ImageBitmap;
  try {
    bitmap = await abrirBitmap(file);
  } catch {
    nota(s, "stop", "No pude abrir esa imagen. Probá con PNG, JPG, BMP o WebP.");
    return;
  }
  if (slots[s]?.url) URL.revokeObjectURL(slots[s]!.url!);
  slots[s] = { blob: file, nombre, url: URL.createObjectURL(file) };
  pintarSlot(s);
  form().querySelector<HTMLElement>('[data-err="imagenes"]')!.textContent = "";
  nota(s, "info", "Revisando qué imagen es…");
  try {
    const r = await revisarTipo(bitmap);
    if (id !== revisionId[s] || slots[s]?.blob !== file) return;
    const pct = Math.round(r.confidence * 100);
    const otro: Slot = s === "radiografia" ? "foto" : "radiografia";
    if (!r.sure) {
      nota(s, "warn", `No estoy seguro de qué imagen es (${pct} %). Revisá que sea una ${SLOT_INFO[s].nombre}.`);
    } else if (r.kind === SLOT_INFO[s].kind) {
      nota(s, "ok", `✓ Parece una ${SLOT_INFO[s].nombre} (${pct} %).`);
    } else if (r.kind === "otra") {
      nota(s, "stop", `No parece una imagen de soldadura (${pct} %). La IA daría resultados sin sentido.`, [
        { label: "Quitarla", main: true, run: () => quitar(s) },
        { label: "Dejarla igual", run: () => nota(s, "warn", "Se deja igual: el resultado de la IA puede no tener sentido.") },
      ]);
    } else {
      nota(s, "warn", `Esto parece una ${SLOT_INFO[otro].nombre} (${pct} %), no una ${SLOT_INFO[s].nombre}.`, [
        { label: `Moverla a ${SLOT_INFO[otro].nombre}`, main: true, run: () => mover(s, otro) },
        { label: "Dejarla acá", run: () => nota(s, "warn", `Se deja como ${SLOT_INFO[s].nombre} aunque parece otra cosa.`) },
      ]);
    }
  } catch (error) {
    nota(s, "warn", `No pude revisar la imagen: ${(error as Error).message}`);
  } finally {
    bitmap.close();
  }
}

function mover(desde: Slot, hacia: Slot) {
  const st = slots[desde];
  if (!st?.blob) return;
  const otra = slots[hacia]; // si ya había una imagen ahí, se intercambian
  quitar(desde);
  quitar(hacia);
  elegir(hacia, st.blob, st.nombre);
  if (otra?.blob) elegir(desde, otra.blob, otra.nombre);
}

function quitar(s: Slot) {
  if (slots[s]?.url) URL.revokeObjectURL(slots[s]!.url!);
  slots[s] = null;
  pintarSlot(s);
}

function errores(e: Partial<Record<string, string>>) {
  for (const el of form().querySelectorAll<HTMLElement>("[data-err]")) el.textContent = e[el.dataset.err!] ?? "";
  const primero = Object.keys(e)[0];
  if (primero && primero !== "imagenes") input(primero)?.focus();
}

function actualizarTramos() {
  const mapa = obrasYTramos(juntas);
  const obra = input("obra").value.trim();
  const tramos = mapa.get(obra) ?? [...new Set([...mapa.values()].flat())];
  $("dl-tramos").innerHTML = tramos.map((t) => `<option value="${esc(t)}"></option>`).join("");
}

async function guardar(then: string) {
  const datos = Object.fromEntries(CAMPOS.map((c) => [c, input(c).value.trim()])) as unknown as DatosJunta;
  const presentes = SLOTS.filter((s) => slots[s]);
  const e = validarJunta(datos, presentes, juntas, editando?.id);
  errores(e);
  if (Object.keys(e).length) return;

  const imagenes: Junta["imagenes"] = {};
  const cambiadas: Slot[] = [];
  for (const s of presentes) {
    const st = slots[s]!;
    if (st.blob) {
      imagenes[s] = { imagenId: await guardarImagen(st.blob), nombre: st.nombre };
      cambiadas.push(s);
    } else imagenes[s] = st.existente;
  }
  let junta: Junta;
  if (editando) {
    // sobre la versión guardada: el análisis pudo terminar mientras se editaba
    const editada = await actualizarJunta(editando.id, (f) => {
      const imgs: Junta["imagenes"] = {};
      for (const s of presentes) imgs[s] = cambiadas.includes(s) ? imagenes[s] : f.imagenes[s];
      const nueva: Junta = { ...f, ...datos, imagenes: imgs };
      if (cambiadas.length) delete nueva.decision; // imagen nueva: hay que volver a revisar y decidir
      return nueva;
    });
    if (!editada) throw new Error("la junta ya no existe");
    junta = editada;
  } else {
    junta = { ...datos, id: nuevoId(), creada: ahora(), imagenes };
    await guardarJunta(junta);
  }
  await registrar({
    juntaId: junta.id,
    accion: editando ? "Edición" : "Carga",
    detalle: editando
      ? `editó los datos${cambiadas.length ? ` y reemplazó ${cambiadas.map((s) => `la ${SLOT_INFO[s].nombre}`).join(" y ")}` : ""}`
      : `cargó la junta con ${presentes.map((s) => SLOT_INFO[s].nombre).join(" y ")}`,
  });
  analizarPendientes();
  if (then === "otra") {
    toast(`Junta ${junta.numero} guardada. La IA la está analizando.`);
    await nuevaCarga({ obra: datos.obra, tramo: datos.tramo, tipoUnion: datos.tipoUnion, material: datos.material, diametro: datos.diametro, espesor: datos.espesor, proceso: datos.proceso });
    input("numero").focus();
  } else {
    location.hash = `#/junta/${junta.id}`;
  }
}

async function nuevaCarga(base: Partial<DatosJunta> = {}) {
  juntas = await listarJuntas();
  editando = null;
  form().reset();
  for (const s of SLOTS) quitar(s);
  for (const [k, v] of Object.entries(base)) input(k).value = v ?? "";
  errores({});
  $("cargar-titulo").textContent = "Cargar soldadura";
  $("dl-obras").innerHTML = [...obrasYTramos(juntas).keys()].map((o) => `<option value="${esc(o)}"></option>`).join("");
  actualizarTramos();
}

/** Abre el formulario vacío, o con una junta para editar. */
export async function renderCargar(id?: string) {
  await nuevaCarga();
  if (!id) {
    input("obra").focus();
    return;
  }
  const j = await leerJunta(id);
  if (!j) {
    toast("No encontré esa junta.");
    return;
  }
  editando = j;
  $("cargar-titulo").textContent = `Editar junta ${j.numero}`;
  for (const c of CAMPOS) input(c).value = j[c];
  actualizarTramos();
  for (const s of SLOTS) {
    const img = j.imagenes[s];
    if (!img) continue;
    const blob = await leerImagen(img.imagenId);
    slots[s] = { blob: null, nombre: img.nombre, existente: img, url: blob ? URL.createObjectURL(blob) : undefined };
    pintarSlot(s);
  }
}

export function iniciarCargar() {
  $<HTMLSelectElement>("sel-union").innerHTML =
    `<option value="">—</option>` + TIPOS_UNION.map((t) => `<option>${t}</option>`).join("");
  input("obra").addEventListener("input", actualizarTramos);
  form().addEventListener("input", (e) => {
    const name = (e.target as HTMLInputElement).name;
    const err = name && form().querySelector<HTMLElement>(`[data-err="${name}"]`);
    if (err) err.textContent = ""; // el error se va apenas se corrige
  });
  form().onsubmit = (e) => {
    e.preventDefault();
    const then = (e.submitter as HTMLElement | null)?.dataset.then ?? "revisar";
    guardar(then).catch((error) => toast(`No pude guardar: ${(error as Error).message}`));
  };
  for (const s of SLOTS) {
    const el = slotEl(s);
    el.querySelector<HTMLInputElement>("input[type=file]")!.onchange = (e) => {
      const f = (e.target as HTMLInputElement).files?.[0];
      (e.target as HTMLInputElement).value = "";
      if (f) elegir(s, f, f.name);
    };
    el.querySelector<HTMLElement>(".slot-remove")!.onclick = () => quitar(s);
    el.ondragover = (e) => (e.preventDefault(), el.classList.add("dragging"));
    el.ondragleave = () => el.classList.remove("dragging");
    el.ondrop = (e) => {
      e.preventDefault();
      el.classList.remove("dragging");
      const f = e.dataTransfer?.files[0];
      if (f) elegir(s, f, f.name);
    };
  }
}

