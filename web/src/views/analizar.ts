/**
 * Pantalla "Analizar rápido": una imagen suelta, sin guardar. El portero dice qué imagen es; si
 * coincide con la pestaña, el detector marca los hallazgos; si no, avisa y deja decidir.
 */
import { verdict, type Finding } from "../core";
import type { ImageKind, PorteroResult } from "../analyze";
import { displayName } from "../labels";
import { abrirBitmap, detectar, revisarTipo } from "../pipeline";
import { montarToolbar } from "../toolbar";
import { Viewer } from "../viewer";
import type { Slot } from "../juntas";
import { $, gate, LEVEL_TEXT, KIND_TEXT } from "./ui";

type Modulo = "radiografias" | "cordones";

const MODULES: Record<Modulo, { slot: Slot; kind: ImageKind; name: string; drop: string; help: string }> = {
  radiografias: {
    slot: "radiografia",
    kind: "radiografia",
    name: "radiografía",
    drop: "Arrastrá una radiografía acá",
    help: "Detecta indicaciones internas: porosidad, fisuras, escoria, falta de penetración y de fusión.",
  },
  cordones: {
    slot: "foto",
    kind: "foto_cordon",
    name: "foto del cordón",
    drop: "Arrastrá una foto del cordón acá",
    help: "Revisa la superficie: cordón bueno, cordón malo y defectos visibles. No ve defectos internos.",
  },
};

let viewer: Viewer;
let toolbar: ReturnType<typeof montarToolbar>;
let modulo: Modulo = "radiografias";
let image: ImageBitmap | null = null;
let findings: Finding[] = [];
let run = 0; // para descartar resultados de un análisis viejo

function status(text: string | null, fraction?: number) {
  const el = $("status");
  el.hidden = text === null;
  if (text === null) return;
  el.innerHTML = "";
  el.append(text);
  if (fraction !== undefined) {
    const bar = document.createElement("progress");
    bar.max = 1;
    bar.value = fraction;
    el.append(bar);
  }
}

function setModulo(next: Modulo) {
  modulo = next;
  for (const b of document.querySelectorAll<HTMLButtonElement>("[data-modulo]")) {
    b.setAttribute("aria-selected", String(b.dataset.modulo === next));
  }
  $("drop-title").textContent = MODULES[next].drop;
  $("module-help").textContent = MODULES[next].help;
}

function showFindings(list: Finding[]) {
  findings = list;
  viewer.setFindings(list);
  const n = (lvl: string) => list.filter((f) => f.level === lvl).length;
  $("n-def").textContent = String(n("defecto"));
  $("n-rev").textContent = String(n("revisar"));
  $("n-ok").textContent = String(n("bien"));
  $("verdict").textContent = verdict(list);
  renderList();
}

function renderList() {
  const ol = $("findings");
  ol.innerHTML = "";
  for (const f of findings) {
    if (f.level === "bien" && !viewer.settings.showGood) continue;
    const li = document.createElement("li");
    li.className = `${f.level}${viewer.selected === f.number ? " selected" : ""}`;
    li.tabIndex = 0;
    li.innerHTML = `<span class="num">${f.number}</span><span>${displayName(f.box.label)}<br><span class="level">${LEVEL_TEXT[f.level]}</span></span><span class="conf">${Math.round((f.box.score ?? 0) * 100)}%</span>`;
    li.onclick = () => {
      viewer.focus(f.number);
      renderList();
    };
    li.onkeydown = (e) => e.key === "Enter" && li.click();
    ol.append(li);
  }
}

function resetResults(text = "Analizando…") {
  $("gate").hidden = true;
  $("verdict").textContent = text;
  for (const id of ["n-def", "n-rev", "n-ok"]) $(id).textContent = "–";
  $("findings").innerHTML = "";
  findings = [];
  viewer.setFindings([]);
}

async function analyze(force = false) {
  if (!image) return;
  const id = ++run;
  const mod = MODULES[modulo];
  resetResults("Revisando qué imagen es…");

  if (!force) {
    let result: PorteroResult;
    try {
      result = await revisarTipo(image);
    } catch (error) {
      status(`No pude revisar la imagen: ${(error as Error).message}`);
      $("verdict").textContent = "Error al analizar";
      return;
    }
    if (id !== run) return;
    const pct = Math.round(result.confidence * 100);
    const other: Modulo = modulo === "radiografias" ? "cordones" : "radiografias";
    if (!result.sure) {
      const p = result.probabilities;
      gate(
        $("gate"),
        `No estoy seguro de qué imagen es (radiografía ${Math.round(p.radiografia * 100)} %, foto de cordón ${Math.round(p.foto_cordon * 100)} %, otra ${Math.round(p.otra * 100)} %).`,
        [
          { label: `Analizar como ${mod.name}`, main: true, run: () => analyze(true) },
          { label: `Cambiar a ${MODULES[other].name}`, run: () => (setModulo(other), analyze(true)) },
        ],
      );
      $("verdict").textContent = "Esperando tu confirmación";
      return;
    }
    if (result.kind === "otra") {
      gate(
        $("gate"),
        `Esto parece ${KIND_TEXT.otra} (${pct} %). No lo analizo para no dar resultados sin sentido.`,
        [{ label: `Analizar igual como ${mod.name}`, run: () => analyze(true) }],
        true,
      );
      $("verdict").textContent = "Imagen no reconocida";
      return;
    }
    if (result.kind !== mod.kind) {
      gate($("gate"), `Esto parece ${KIND_TEXT[result.kind]} (${pct} %), no una ${mod.name}.`, [
        { label: `Cambiar a ${MODULES[other].name}`, main: true, run: () => (setModulo(other), analyze(true)) },
        { label: `Analizar igual como ${mod.name}`, run: () => analyze(true) },
      ]);
      $("verdict").textContent = "Esperando tu confirmación";
      return;
    }
  }

  resetResults("Analizando…");
  try {
    const r = await detectar(mod.slot, image, (done, total) => {
      if (total > 1) status(`Analizando la placa por partes: ${done} de ${total}`, done / total);
    });
    status(null);
    if (id !== run) return;
    showFindings(r.findings);
  } catch (error) {
    status(`No pude analizar: ${(error as Error).message}`);
    $("verdict").textContent = "Error al analizar";
  }
}

async function open(file: File | undefined) {
  if (!file) return;
  try {
    image = await abrirBitmap(file);
  } catch {
    status("No pude abrir esa imagen. Probá con PNG, JPG, BMP o WebP.");
    return;
  }
  status(null);
  $("empty").hidden = true;
  viewer.setImage(image);
  analyze();
}

export function iniciarAnalizar() {
  viewer = new Viewer($<HTMLCanvasElement>("viewer"));
  toolbar = montarToolbar(
    document.querySelector<HTMLElement>('[data-view="analizar"] [data-toolbar]')!,
    "",
    () => [viewer],
    `<label class="check"><input id="show-good" type="checkbox" checked /> Zonas sanas</label>`,
  );
  viewer.onZoom = () => toolbar.updateZoom();
  viewer.onSelect = () => renderList();
  $<HTMLInputElement>("show-good").onchange = (e) => {
    viewer.update({ showGood: (e.target as HTMLInputElement).checked });
    renderList();
  };
  for (const b of document.querySelectorAll<HTMLButtonElement>("[data-modulo]")) {
    b.onclick = () => {
      if (b.dataset.modulo === modulo) return;
      setModulo(b.dataset.modulo as Modulo);
      if (image) analyze();
    };
  }
  for (const id of ["file", "file2"]) {
    $<HTMLInputElement>(id).onchange = (e) => open((e.target as HTMLInputElement).files?.[0]);
  }
  const drop = $("drop");
  drop.ondragover = (e) => (e.preventDefault(), drop.classList.add("dragging"));
  drop.ondragleave = () => drop.classList.remove("dragging");
  drop.ondrop = (e) => {
    e.preventDefault();
    drop.classList.remove("dragging");
    open(e.dataTransfer?.files[0]);
  };
  setModulo("radiografias");
  return toolbar;
}

