/**
 * Pantalla "Analizar": el portero dice qué imagen es; si coincide con la pestaña, el detector
 * correspondiente marca los hallazgos; si no, la app avisa y deja decidir al usuario.
 */
import { classify, verdict, type Finding } from "./core";
import { detect, identify, type ImageKind, type PorteroResult } from "./analyze";
import { displayName } from "./labels";
import { loadModel, type DetectorConfig, type ModelName, type PorteroConfig } from "./models";
import { Viewer } from "./viewer";

type Modulo = "radiografias" | "cordones";

const MODULES: Record<Modulo, { kind: ImageKind; name: string; drop: string; help: string; size: string }> = {
  radiografias: {
    kind: "radiografia",
    name: "radiografía",
    drop: "Arrastrá una radiografía acá",
    help: "Detecta indicaciones internas: porosidad, fisuras, escoria, falta de penetración y de fusión.",
    size: "81 MB",
  },
  cordones: {
    kind: "foto_cordon",
    name: "foto del cordón",
    drop: "Arrastrá una foto del cordón acá",
    help: "Revisa la superficie: cordón bueno, cordón malo y defectos visibles. No ve defectos internos.",
    size: "81 MB",
  },
};
const KIND_TEXT: Record<ImageKind, string> = {
  radiografia: "una radiografía de soldadura",
  foto_cordon: "una foto de cordón",
  otra: "otra cosa (ni radiografía de soldadura ni foto de cordón)",
};
const LEVEL_TEXT = { defecto: "Posible defecto", revisar: "Revisar", bien: "Bien" };
const DEFAULT_HIGH = 0.5; // provisorio: solo decide rojo o amarillo, nunca oculta

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const viewer = new Viewer($<HTMLCanvasElement>("viewer"));
let modulo: Modulo = "radiografias";
let image: ImageBitmap | null = null;
let findings: Finding[] = [];
let run = 0; // para descartar resultados de un análisis viejo

// ------------------------------------------------------------------ estado en pantalla

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

function gate(message: string, actions: { label: string; main?: boolean; run: () => void }[], stop = false) {
  const el = $("gate");
  el.hidden = false;
  el.className = `gate${stop ? " stop" : ""}`;
  el.innerHTML = "";
  const p = document.createElement("div");
  p.textContent = message;
  const row = document.createElement("div");
  row.className = "actions";
  for (const a of actions) {
    const b = document.createElement("button");
    b.textContent = a.label;
    if (a.main) b.className = "main";
    b.onclick = () => {
      el.hidden = true;
      a.run();
    };
    row.append(b);
  }
  el.append(p, row);
}

function setModulo(next: Modulo) {
  modulo = next;
  for (const b of document.querySelectorAll<HTMLButtonElement>(".tabs button")) {
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

// ------------------------------------------------------------------ flujo

async function withModel<C>(name: ModelName, label: string, size: string) {
  let shown = false;
  const model = await loadModel<C>(name, (f) => {
    if (f < 1) {
      shown = true;
      status(`Bajando ${label} (${size}). Solo la primera vez; después queda guardado.`, f);
    }
  });
  if (shown) status(null);
  return model;
}

async function analyze(force = false) {
  if (!image) return;
  const id = ++run;
  const mod = MODULES[modulo];
  resetResults("Revisando qué imagen es…");

  if (!force) {
    let result: PorteroResult;
    try {
      const portero = await withModel<PorteroConfig>("portero", "el portero", "6 MB");
      result = await identify(portero, image);
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
        `Esto parece ${KIND_TEXT.otra} (${pct} %). No lo analizo para no dar resultados sin sentido.`,
        [{ label: `Analizar igual como ${mod.name}`, run: () => analyze(true) }],
        true,
      );
      $("verdict").textContent = "Imagen no reconocida";
      return;
    }
    if (result.kind !== mod.kind) {
      gate(`Esto parece ${KIND_TEXT[result.kind]} (${pct} %), no una ${mod.name}.`, [
        { label: `Cambiar a ${MODULES[other].name}`, main: true, run: () => (setModulo(other), analyze(true)) },
        { label: `Analizar igual como ${mod.name}`, run: () => analyze(true) },
      ]);
      $("verdict").textContent = "Esperando tu confirmación";
      return;
    }
  }

  resetResults("Analizando…");
  try {
    const detector = await withModel<DetectorConfig>(modulo, `el modelo de ${mod.name}`, mod.size);
    if (id !== run) return;
    const boxes = await detect(detector, image, (done, total) => {
      if (total > 1) status(`Analizando la placa por partes: ${done} de ${total}`, done / total);
    });
    status(null);
    if (id !== run) return;
    showFindings(classify(boxes, detector.config.umbral_alto ?? DEFAULT_HIGH));
  } catch (error) {
    status(`No pude analizar: ${(error as Error).message}`);
    $("verdict").textContent = "Error al analizar";
  }
}

async function open(file: File | undefined) {
  if (!file) return;
  try {
    // sin conversión de color: los píxeles tal cual vienen en el archivo, como los lee Pillow
    image = await createImageBitmap(file, { colorSpaceConversion: "none", premultiplyAlpha: "none" });
  } catch {
    status("No pude abrir esa imagen. Probá con PNG, JPG, BMP o WebP.");
    return;
  }
  status(null);
  $("empty").hidden = true;
  viewer.setImage(image);
  updateZoom();
  analyze();
}

// ------------------------------------------------------------------ controles

function updateZoom() {
  $("zoom-level").textContent = `${Math.round(viewer.zoom * 100)} %`;
}

for (const b of document.querySelectorAll<HTMLButtonElement>(".tabs button")) {
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

$("zoom-in").onclick = () => (viewer.zoomBy(1.25), updateZoom());
$("zoom-out").onclick = () => (viewer.zoomBy(0.8), updateZoom());
$("fit").onclick = () => (viewer.fit(), updateZoom());
$("viewer").addEventListener("wheel", () => updateZoom());
$<HTMLInputElement>("brightness").oninput = (e) => viewer.update({ brightness: Number((e.target as HTMLInputElement).value) });
$<HTMLInputElement>("contrast").oninput = (e) => viewer.update({ contrast: Number((e.target as HTMLInputElement).value) });
$<HTMLInputElement>("invert").onchange = (e) => viewer.update({ invert: (e.target as HTMLInputElement).checked });
$<HTMLInputElement>("show-good").onchange = (e) => {
  viewer.update({ showGood: (e.target as HTMLInputElement).checked });
  renderList();
};
$("reset-view").onclick = () => {
  $<HTMLInputElement>("brightness").value = "1";
  $<HTMLInputElement>("contrast").value = "1";
  $<HTMLInputElement>("invert").checked = false;
  viewer.update({ brightness: 1, contrast: 1, invert: false });
};
viewer.onSelect = () => renderList();
document.addEventListener("keydown", (e) => {
  if ((e.target as HTMLElement).tagName === "INPUT") return;
  if (e.key === "+" || e.key === "=") $("zoom-in").click();
  if (e.key === "-") $("zoom-out").click();
  if (e.key === "0") $("fit").click();
});

setModulo("radiografias");
