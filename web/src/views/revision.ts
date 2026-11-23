/**
 * Revisión de una junta: visor (Radiografía · Foto · Lado a lado), revisión de cada hallazgo y
 * decisión del inspector, que queda bloqueada hasta revisar todo. Cada paso va al historial.
 */
import {
  confirmados,
  decidir,
  ESTADOS,
  estado,
  labelFinal,
  necesitaRevision,
  pendientes,
  puedeDecidir,
  reabrir,
  RESULTADOS,
  revisarHallazgo,
  SLOTS,
  type Accion,
  type Hallazgo,
  type Junta,
  type Resultado,
  type Slot,
} from "../juntas";
import { displayName, TIPOS_POR_IMAGEN } from "../labels";
import { abrirBitmap, alCambiar, analizarPendientes, SLOT_INFO } from "../pipeline";
import { actualizarJunta, ajustes, borrarJunta, historial, leerImagen, leerJunta, registrar } from "../store";
import { montarToolbar, type Toolbar } from "../toolbar";
import { Viewer } from "../viewer";
import { imprimirInforme } from "./informe";
import { abrirAjustes } from "./ajustes";
import { $, esc, fecha, LEVEL_TEXT, toast } from "./ui";

type Vista = Slot | "lado";

let junta: Junta | null = null;
let vista: Vista = "radiografia";
const viewers = {} as Record<Slot, Viewer>;
const cargadas: Partial<Record<Slot, string>> = {}; // imagenId mostrada en cada visor
const bitmaps = new Map<string, ImageBitmap>();
let toolbar: Toolbar;
let borrarArmado = 0;

const visibles = (): Slot[] => (vista === "lado" ? SLOTS.filter((s) => junta?.imagenes[s]) : [vista]);

export async function bitmapDe(imagenId: string): Promise<ImageBitmap | null> {
  if (bitmaps.has(imagenId)) return bitmaps.get(imagenId)!;
  const blob = await leerImagen(imagenId);
  if (!blob) return null;
  const b = await abrirBitmap(blob);
  bitmaps.set(imagenId, b);
  return b;
}

function setVista(v: Vista) {
  vista = v;
  for (const b of document.querySelectorAll<HTMLButtonElement>("#r-vistas button")) {
    b.setAttribute("aria-selected", String(b.dataset.vista === v));
  }
  $("r-viewers").classList.toggle("lado", v === "lado");
  for (const s of SLOTS) {
    document.querySelector<HTMLElement>(`[data-pane="${s}"]`)!.hidden = !visibles().includes(s);
  }
  requestAnimationFrame(() => {
    for (const s of visibles()) viewers[s].fit();
    toolbar.updateZoom();
  });
}

async function pintarVisores() {
  if (!junta) return;
  for (const s of SLOTS) {
    const img = junta.imagenes[s];
    const pane = document.querySelector<HTMLElement>(`[data-pane="${s}"]`)!;
    const msg = pane.querySelector<HTMLElement>(".pane-msg")!;
    if (!img) {
      viewers[s].clear();
      delete cargadas[s];
      msg.hidden = false;
      msg.textContent = `Esta junta no tiene ${SLOT_INFO[s].nombre}.`;
      continue;
    }
    if (cargadas[s] !== img.imagenId) {
      const b = await bitmapDe(img.imagenId);
      if (b) viewers[s].setImage(b);
      cargadas[s] = img.imagenId;
    }
    msg.hidden = !!img.analisis;
    msg.textContent = img.error ? `No se pudo analizar: ${img.error}` : "La IA está analizando esta imagen…";
    viewers[s].setFindings(img.analisis?.hallazgos ?? []);
  }
}

function hallazgoHTML(s: Slot, h: Hallazgo, decidida: boolean): HTMLLIElement {
  const li = document.createElement("li");
  const sel = viewers[s].selected === h.number && visibles().includes(s);
  li.className = `${h.level} rev-${h.revision}${sel ? " selected" : ""}`;
  li.dataset.slot = s;
  li.dataset.number = String(h.number);
  const cambiado = h.labelInspector
    ? `<s class="muted">${esc(displayName(h.box.label))}</s> → ${esc(displayName(h.labelInspector))}`
    : esc(displayName(h.box.label));
  const estadoRev =
    h.revision === "aceptado" ? `<span class="rev ok">✓ Aceptado</span>` : h.revision === "descartado" ? `<span class="rev no">✕ Descartado</span>` : "";
  li.innerHTML = `
    <span class="num">${h.number}</span>
    <span><span class="nombre">${cambiado}</span><br><span class="level">${LEVEL_TEXT[h.level]}</span> ${estadoRev}</span>
    <span class="conf">${Math.round((h.box.score ?? 0) * 100)}%</span>`;
  li.tabIndex = 0;
  li.onclick = (e) => {
    if ((e.target as HTMLElement).closest(".acciones")) return;
    if (!visibles().includes(s)) setVista(s);
    requestAnimationFrame(() => {
      viewers[s].focus(h.number);
      for (const o of SLOTS) if (o !== s) viewers[o].selected = null;
      pintarHallazgos();
      toolbar.updateZoom();
    });
  };
  if (necesitaRevision(h) && !decidida) {
    const acc = document.createElement("div");
    acc.className = "acciones";
    if (h.revision === "pendiente") {
      acc.append(boton("✓ Aceptar", "ok", () => accion(s, h.number, "aceptar"), `aceptar-${s}-${h.number}`));
      acc.append(boton("✕ Descartar", "no", () => accion(s, h.number, "descartar"), `descartar-${s}-${h.number}`));
    } else {
      acc.append(boton("Deshacer", "", () => accion(s, h.number, "deshacer")));
    }
    const select = document.createElement("select");
    select.title = "Cambiar el tipo (lo acepta con el tipo nuevo)";
    select.innerHTML =
      `<option value="">Cambiar tipo…</option>` +
      TIPOS_POR_IMAGEN[s].map((t) => `<option value="${t}"${t === labelFinal(h) ? " disabled" : ""}>${displayName(t)}</option>`).join("");
    select.onchange = () => select.value && accion(s, h.number, "cambiar", select.value);
    acc.append(select);
    li.append(acc);
  }
  return li;
}

function boton(texto: string, clase: string, fn: () => void, testId?: string) {
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = texto;
  if (clase) b.className = clase;
  if (testId) b.dataset.test = testId;
  b.onclick = fn;
  return b;
}

function pintarHallazgos() {
  if (!junta) return;
  const ol = $("r-hallazgos");
  ol.innerHTML = "";
  const showGood = $<HTMLInputElement>("r-show-good").checked;
  const conImagen = SLOTS.filter((s) => junta!.imagenes[s]);
  for (const s of conImagen) {
    const a = junta.imagenes[s]!.analisis;
    if (conImagen.length > 1) {
      const head = document.createElement("li");
      head.className = "group";
      head.textContent = SLOT_INFO[s].nombre.charAt(0).toUpperCase() + SLOT_INFO[s].nombre.slice(1);
      ol.append(head);
    }
    if (!a) {
      const li = document.createElement("li");
      li.className = "group muted";
      li.textContent = junta.imagenes[s]!.error ? "No se pudo analizar." : "Analizando…";
      ol.append(li);
      continue;
    }
    const lista = a.hallazgos.filter((h) => showGood || h.level !== "bien");
    if (!lista.length) {
      const li = document.createElement("li");
      li.className = "group muted";
      li.textContent = a.hallazgos.length ? "Solo zonas sanas." : "La IA no marcó nada.";
      ol.append(li);
    }
    for (const h of lista) ol.append(hallazgoHTML(s, h, !!junta.decision));
  }
  const n = pendientes(junta);
  $("r-pend").textContent = n ? `· faltan ${n}` : "";
}

function pintarEstado() {
  if (!junta) return;
  const e = estado(junta);
  const el = $("r-estado");
  el.className = `estado-box est-${e}`;
  if (junta.decision) {
    const d = junta.decision;
    el.innerHTML = `<strong>${RESULTADOS[d.resultado]}</strong><br><small>Decidió ${esc(d.inspector)} el ${fecha(d.fecha)} · Norma: ${esc(d.norma)}</small>${d.nota ? `<p>${esc(d.nota)}</p>` : ""}`;
  } else {
    el.innerHTML = `<strong>${ESTADOS[e]}</strong>${e === "para_revisar" ? `<br><small>Revisá cada hallazgo para poder decidir.</small>` : ""}`;
  }
}

function pintarDecision() {
  if (!junta) return;
  const el = $("r-decision");
  if (junta.decision) {
    el.innerHTML = "";
    el.append(boton("Reabrir la junta", "secondary", reabrirJunta, "reabrir"));
    return;
  }
  const p = puedeDecidir(junta);
  const aj = ajustes();
  const n = confirmados(junta).length;
  el.innerHTML = `
    <h3>Decisión del inspector</h3>
    <div class="radios" role="radiogroup" aria-label="Resultado">
      ${(Object.keys(RESULTADOS) as Resultado[])
        .map((r) => `<label class="radio res-${r}"><input type="radio" name="resultado" value="${r}" ${p.ok ? "" : "disabled"}> ${RESULTADOS[r]}</label>`)
        .join("")}
    </div>
    <label>Nota / motivo <textarea id="r-nota" rows="2" ${p.ok ? "" : "disabled"} placeholder="Obligatoria para reparar o rechazar"></textarea></label>
    <p class="help small">Inspector: <strong>${esc(aj.inspector || "sin nombre")}</strong> · Norma: <strong>${esc(aj.norma)}</strong> · <button type="button" class="link" id="r-cambiar-insp">cambiar</button></p>
    ${n ? `<p class="help small">Confirmaste ${n} defecto${n > 1 ? "s" : ""}. Si igual cumple la norma, podés aprobarla.</p>` : ""}
    <p class="err" id="r-dec-err">${p.ok ? "" : esc(p.motivo ?? "")}</p>
    <button type="button" class="primary" id="r-decidir" ${p.ok ? "" : "disabled"}>Registrar decisión</button>`;
  $("r-cambiar-insp").onclick = () => abrirAjustes(() => pintarDecision());
  $("r-decidir").onclick = registrarDecision;
}

async function pintarHistorial() {
  if (!junta) return;
  const ev = await historial(junta.id);
  $("r-historial").innerHTML = ev
    .slice()
    .reverse()
    .map((e) => `<li><span class="muted">${fecha(e.fecha)}</span> <strong>${esc(e.quien)}</strong> ${esc(e.detalle)}</li>`)
    .join("");
}

function pintarCabecera() {
  if (!junta) return;
  const j = junta;
  $("r-titulo").innerHTML = `Junta ${esc(j.numero)} ${j.ejemplo ? `<small class="tag">ejemplo</small>` : ""}`;
  $("r-sub").textContent = `${j.obra} · ${j.tramo}`;
  const filas: [string, string][] = [
    ["Progresiva", j.progresiva],
    ["Unión", j.tipoUnion],
    ["Material", j.material],
    ["Diámetro", j.diametro],
    ["Espesor", j.espesor],
    ["Proceso", j.proceso],
    ["Soldador", j.soldador],
  ];
  $("r-datos").innerHTML =
    filas
      .filter(([, v]) => v)
      .map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`)
      .join("") + `<div class="edit"><a class="link" href="#/editar/${j.id}">Editar datos</a></div>`;
  for (const b of document.querySelectorAll<HTMLButtonElement>("#r-vistas button")) {
    const v = b.dataset.vista as Vista;
    b.disabled = v === "lado" ? SLOTS.some((s) => !j.imagenes[s]) : !j.imagenes[v];
  }
}

async function pintarTodo() {
  pintarCabecera();
  await pintarVisores();
  pintarHallazgos();
  pintarEstado();
  pintarDecision();
  await pintarHistorial();
}

// Los cambios del inspector van en fila y siempre sobre la junta guardada (no sobre la copia en
// pantalla), así un doble clic o la IA terminando de analizar no pisan nada.
let fila: Promise<unknown> = Promise.resolve();

function cambiar(fn: (j: Junta) => { junta: Junta; detalle: string }, accionTxt: string): Promise<Junta | undefined> {
  const id = junta?.id;
  if (!id) return Promise.resolve(undefined);
  const tarea = fila.then(async () => {
    let detalle = "";
    const nueva = await actualizarJunta(id, (j) => {
      const r = fn(j);
      detalle = r.detalle;
      return r.junta;
    });
    if (!nueva) return undefined;
    await registrar({ juntaId: id, accion: accionTxt, detalle });
    if (junta?.id === id) {
      junta = nueva;
      await pintarTodo();
    }
    return nueva;
  });
  fila = tarea.catch(() => undefined);
  return tarea;
}

async function accion(s: Slot, number: number, a: Accion, label?: string) {
  try {
    await cambiar((j) => revisarHallazgo(j, s, number, a, label), "Revisión");
  } catch (error) {
    toast((error as Error).message);
  }
}

async function registrarDecision() {
  if (!junta) return;
  const resultado = document.querySelector<HTMLInputElement>('input[name="resultado"]:checked')?.value as Resultado | undefined;
  const err = $("r-dec-err");
  if (!resultado) {
    err.textContent = "Elegí un resultado.";
    return;
  }
  const aj = ajustes();
  if (!aj.inspector.trim()) {
    err.textContent = "Antes de decidir, poné tu nombre de inspector.";
    abrirAjustes(() => pintarDecision());
    return;
  }
  try {
    const notaTxt = $<HTMLTextAreaElement>("r-nota").value;
    const nueva = await cambiar((j) => {
      const d = decidir(j, { resultado, nota: notaTxt, inspector: aj.inspector, norma: aj.norma, fecha: new Date().toISOString() });
      const nota = d.decision!.nota;
      return { junta: d, detalle: `decidió: ${RESULTADOS[resultado].toLowerCase()} (${aj.norma})${nota ? ` · "${nota}"` : ""}` };
    }, "Decisión");
    if (nueva) {
      toast(`Junta ${nueva.numero}: ${RESULTADOS[resultado].toLowerCase()}.`);
      document.querySelector('[data-view="junta"] .panel')!.scrollTo({ top: 0, behavior: "smooth" });
    }
  } catch (error) {
    err.textContent = (error as Error).message;
  }
}

async function reabrirJunta() {
  await cambiar((j) => ({ junta: reabrir(j), detalle: "reabrió la junta (la decisión anterior queda en el historial)" }), "Reapertura");
}

export async function renderRevision(id: string) {
  const j = await leerJunta(id);
  if (!j) {
    toast("No encontré esa junta.");
    location.hash = "#/bandeja";
    return;
  }
  const otra = junta?.id !== j.id;
  junta = j;
  borrarArmado = 0;
  $("r-borrar").textContent = "Borrar junta";
  if (otra) {
    for (const s of SLOTS) viewers[s].selected = null;
    setVista(j.imagenes.radiografia ? "radiografia" : "foto");
  }
  await pintarTodo();
  if (otra) setVista(vista);
  if (SLOTS.some((s) => j.imagenes[s] && !j.imagenes[s]!.analisis)) analizarPendientes();
}

export function iniciarRevision() {
  for (const s of SLOTS) {
    viewers[s] = new Viewer($<HTMLCanvasElement>(`r-canvas-${s}`));
    viewers[s].onZoom = () => toolbar?.updateZoom();
    viewers[s].onSelect = () => pintarHallazgos();
  }
  toolbar = montarToolbar(document.querySelector<HTMLElement>("[data-toolbar='r-']")!, "r-", () => visibles().map((s) => viewers[s]));
  for (const b of document.querySelectorAll<HTMLButtonElement>("#r-vistas button")) {
    b.onclick = () => setVista(b.dataset.vista as Vista);
  }
  $<HTMLInputElement>("r-show-good").onchange = (e) => {
    const on = (e.target as HTMLInputElement).checked;
    for (const s of SLOTS) viewers[s].update({ showGood: on });
    pintarHallazgos();
  };
  $("r-informe").onclick = async () => {
    if (!junta) return;
    await imprimirInforme(junta, await historial(junta.id));
  };
  $("r-borrar").onclick = async () => {
    if (!junta) return;
    if (Date.now() - borrarArmado > 4000) {
      borrarArmado = Date.now();
      $("r-borrar").textContent = "¿Seguro? Tocá de nuevo para borrar";
      return;
    }
    await borrarJunta(junta);
    toast(`Junta ${junta.numero} borrada.`);
    junta = null;
    location.hash = "#/bandeja";
  };
  alCambiar((id) => {
    if (junta?.id === id && location.hash.startsWith("#/junta/")) renderRevision(id);
  });
}

export const toolbarRevision = () => toolbar;
