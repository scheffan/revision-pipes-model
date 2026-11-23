/**
 * Barra del visor (zoom, brillo, contraste, invertir). La misma barra maneja uno o dos visores
 * (vista "Lado a lado").
 */
import type { Viewer } from "./viewer";

export interface Toolbar {
  updateZoom(): void;
  zoomIn(): void;
  zoomOut(): void;
  fit(): void;
}

export function montarToolbar(el: HTMLElement, prefix: string, viewers: () => Viewer[], extra = ""): Toolbar {
  el.innerHTML = `
    <button data-t="zoom-out" title="Alejar (−)" aria-label="Alejar">−</button>
    <span data-t="zoom-level" class="zoom">100 %</span>
    <button data-t="zoom-in" title="Acercar (+)" aria-label="Acercar">+</button>
    <button data-t="fit" title="Ver entera (0)">Ajustar</button>
    <span class="sep"></span>
    <label>Brillo <input data-t="brightness" type="range" min="0.3" max="2.5" step="0.05" value="1" /></label>
    <label>Contraste <input data-t="contrast" type="range" min="0.3" max="3" step="0.05" value="1" /></label>
    <label class="check"><input data-t="invert" type="checkbox" /> Invertir</label>
    ${extra}
    <button data-t="reset-view" title="Restablecer brillo y contraste">Restablecer</button>`;
  // ids estables para pruebas y accesibilidad
  for (const c of el.querySelectorAll<HTMLElement>("[data-t]")) c.id = `${prefix}${c.dataset.t}`;
  const q = <T extends HTMLElement>(t: string) => el.querySelector<T>(`[data-t="${t}"]`)!;
  const all = (fn: (v: Viewer) => void) => viewers().forEach(fn);

  const updateZoom = () => {
    const v = viewers()[0];
    q("zoom-level").textContent = v ? `${Math.round(v.zoom * 100)} %` : "–";
  };
  const zoomIn = () => (all((v) => v.zoomBy(1.25)), updateZoom());
  const zoomOut = () => (all((v) => v.zoomBy(0.8)), updateZoom());
  const fit = () => (all((v) => v.fit()), updateZoom());
  q("zoom-in").onclick = zoomIn;
  q("zoom-out").onclick = zoomOut;
  q("fit").onclick = fit;
  const range = (t: string) => Number(q<HTMLInputElement>(t).value);
  q<HTMLInputElement>("brightness").oninput = () => all((v) => v.update({ brightness: range("brightness") }));
  q<HTMLInputElement>("contrast").oninput = () => all((v) => v.update({ contrast: range("contrast") }));
  q<HTMLInputElement>("invert").onchange = (e) => all((v) => v.update({ invert: (e.target as HTMLInputElement).checked }));
  q("reset-view").onclick = () => {
    q<HTMLInputElement>("brightness").value = "1";
    q<HTMLInputElement>("contrast").value = "1";
    q<HTMLInputElement>("invert").checked = false;
    all((v) => v.update({ brightness: 1, contrast: 1, invert: false }));
  };
  return { updateZoom, zoomIn, zoomOut, fit };
}
