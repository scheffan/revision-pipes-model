/** Diálogo "Inspector y norma": quedan registrados en cada revisión y decisión. */
import { ajustes, guardarAjustes, NORMAS } from "../store";
import { $ } from "./ui";

export function pintarResumenAjustes() {
  const a = ajustes();
  $("ajustes-resumen").textContent = `Inspector: ${a.inspector || "sin nombre"} · ${a.norma}`;
}

export function abrirAjustes(despues?: () => void) {
  const dlg = $<HTMLDialogElement>("dlg-ajustes");
  const a = ajustes();
  $<HTMLInputElement>("aj-inspector").value = a.inspector;
  $<HTMLSelectElement>("aj-norma").value = a.norma;
  dlg.onclose = () => {
    if (dlg.returnValue === "ok") {
      guardarAjustes({ inspector: $<HTMLInputElement>("aj-inspector").value.trim(), norma: $<HTMLSelectElement>("aj-norma").value });
      pintarResumenAjustes();
      despues?.();
    }
  };
  dlg.returnValue = "";
  dlg.showModal();
  $<HTMLInputElement>("aj-inspector").focus();
}

export function iniciarAjustes() {
  $<HTMLSelectElement>("aj-norma").innerHTML = NORMAS.map((n) => `<option>${n}</option>`).join("");
  $("btn-ajustes").onclick = () => abrirAjustes();
  pintarResumenAjustes();
}
