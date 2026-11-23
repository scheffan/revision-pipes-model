/** Utilidades de pantalla compartidas. */
import type { ImageKind } from "../analyze";

export const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

export const LEVEL_TEXT = { defecto: "Posible defecto", revisar: "Revisar", bien: "Sano" } as const;

export const KIND_TEXT: Record<ImageKind, string> = {
  radiografia: "una radiografía de soldadura",
  foto_cordon: "una foto de cordón",
  otra: "otra cosa (ni radiografía de soldadura ni foto de cordón)",
};

/** Escapa texto del usuario antes de meterlo en HTML. */
export function esc(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

export function fecha(iso: string, conHora = true): string {
  const d = new Date(iso);
  return d.toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    ...(conHora ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
}

export function gate(
  el: HTMLElement,
  message: string,
  actions: { label: string; main?: boolean; run: () => void }[],
  stop = false,
) {
  el.hidden = false;
  el.className = `gate${stop ? " stop" : ""}`;
  el.innerHTML = "";
  const p = document.createElement("div");
  p.textContent = message;
  const row = document.createElement("div");
  row.className = "actions";
  for (const a of actions) {
    const b = document.createElement("button");
    b.type = "button";
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

/** Barra de estado de arriba (descargas de modelos y análisis en curso). */
export function globalStatus(text: string | null, fraction?: number) {
  const el = $("global-status");
  el.hidden = text === null;
  if (text === null) return;
  el.innerHTML = "";
  const span = document.createElement("span");
  span.textContent = text;
  el.append(span);
  if (fraction !== undefined) {
    const bar = document.createElement("progress");
    bar.max = 1;
    bar.value = fraction;
    el.append(bar);
  }
}

let toastTimer = 0;
export function toast(text: string) {
  let el = document.getElementById("toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    el.className = "toast";
    el.setAttribute("role", "status");
    document.body.append(el);
  }
  el.textContent = text;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => el!.classList.remove("show"), 3500);
}
