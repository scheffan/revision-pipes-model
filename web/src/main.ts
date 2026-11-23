/**
 * App del inspector: Bandeja · Cargar soldadura · Revisión de una junta · Analizar rápido.
 * Navegación por el hash de la URL (#/bandeja, #/cargar, #/junta/<id>, #/editar/<id>, #/analizar),
 * así funciona en GitHub Pages sin servidor.
 */
import { alCambiar, alProgresar, analizarPendientes } from "./pipeline";
import { iniciarAjustes } from "./views/ajustes";
import { iniciarAnalizar } from "./views/analizar";
import { iniciarBandeja, renderBandeja } from "./views/bandeja";
import { iniciarCargar, renderCargar } from "./views/cargar";
import { iniciarRevision, renderRevision, toolbarRevision } from "./views/revision";
import { globalStatus } from "./views/ui";

type View = "bandeja" | "cargar" | "junta" | "analizar";
let actual: View = "bandeja";

async function route() {
  const [, view = "bandeja", id] = location.hash.replace(/^#\/?/, "#/").split("/");
  const v: View = view === "editar" ? "cargar" : (["bandeja", "cargar", "junta", "analizar"] as View[]).includes(view as View) ? (view as View) : "bandeja";
  actual = v;
  for (const el of document.querySelectorAll<HTMLElement>("[data-view]")) el.hidden = el.dataset.view !== v;
  for (const a of document.querySelectorAll<HTMLElement>("[data-nav]")) {
    a.classList.toggle("active", a.dataset.nav === (v === "junta" ? "bandeja" : v));
    if (a.dataset.nav === v) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  }
  if (v === "bandeja") await renderBandeja();
  if (v === "cargar") await renderCargar(view === "editar" ? id : undefined);
  if (v === "junta" && id) await renderRevision(id);
  window.scrollTo(0, 0);
}

alProgresar(globalStatus);
iniciarAjustes();
iniciarBandeja();
iniciarCargar();
iniciarRevision();
const toolbarAnalizar = iniciarAnalizar();
alCambiar(() => actual === "bandeja" && renderBandeja());

document.addEventListener("keydown", (e) => {
  const t = e.target as HTMLElement;
  if (["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName)) return;
  const tb = actual === "analizar" ? toolbarAnalizar : actual === "junta" ? toolbarRevision() : null;
  if (!tb) return;
  if (e.key === "+" || e.key === "=") tb.zoomIn();
  if (e.key === "-") tb.zoomOut();
  if (e.key === "0") tb.fit();
});

window.addEventListener("hashchange", route);
route().then(() => analizarPendientes()); // retoma lo que haya quedado sin analizar
