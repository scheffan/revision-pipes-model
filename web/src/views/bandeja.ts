/** Bandeja: juntas filtradas por obra, tramo y estado, ordenadas por riesgo. */
import { cargarEjemplo } from "../ejemplo";
import { ESTADOS, estado, grupoRiesgo, obrasYTramos, ordenarBandeja, pendientes, resumenIA, SLOTS, type Junta } from "../juntas";
import { analizarPendientes, SLOT_INFO } from "../pipeline";
import { exportar, importar, listarJuntas } from "../store";
import { $, esc, toast } from "./ui";

const RIESGO = [
  { clase: "defecto", texto: "Alto" },
  { clase: "revisar", texto: "Medio" },
  { clase: "pendiente", texto: "—" },
  { clase: "bien", texto: "Bajo" },
  { clase: "decidida", texto: "—" },
];
const RESULTADO_CORTO = { aprobada: "Aprobada", reparar: "Reparar", rechazada: "Rechazada" };

let juntas: Junta[] = [];

function opciones(sel: HTMLSelectElement, valores: string[], todos: string) {
  const actual = sel.value;
  sel.innerHTML = `<option value="">${todos}</option>` + valores.map((v) => `<option>${esc(v)}</option>`).join("");
  sel.value = valores.includes(actual) ? actual : "";
}

function queVio(j: Junta): string {
  const img = SLOTS.map((s) => j.imagenes[s]).filter(Boolean);
  if (img.some((i) => i!.error && !i!.analisis)) return `<span class="err-text">Error al analizar</span>`;
  if (img.some((i) => !i!.analisis)) return `<span class="muted">Analizando…</span>`;
  const r = resumenIA(j);
  const partes = [];
  if (r.defectos) partes.push(`<strong>${r.defectos}</strong> posible${r.defectos > 1 ? "s" : ""} defecto${r.defectos > 1 ? "s" : ""} (hasta ${Math.round(r.maxDefecto * 100)} %)`);
  if (r.revisar) partes.push(`${r.revisar} para revisar`);
  return partes.join(" · ") || `<span class="muted">Sin hallazgos</span>`;
}

function estadoHTML(j: Junta): string {
  const e = estado(j);
  if (e === "decidida") {
    const r = j.decision!.resultado;
    return `<span class="badge res-${r}">${RESULTADO_CORTO[r]}</span>`;
  }
  const n = pendientes(j);
  return `<span class="badge est-${e}">${ESTADOS[e]}${e === "para_revisar" ? ` · ${n}` : ""}</span>`;
}

export async function renderBandeja() {
  juntas = await listarJuntas();
  const mapa = obrasYTramos(juntas);
  const fObra = $<HTMLSelectElement>("f-obra");
  const fTramo = $<HTMLSelectElement>("f-tramo");
  opciones(fObra, [...mapa.keys()], "Todas");
  const tramos = fObra.value ? mapa.get(fObra.value) ?? [] : [...new Set([...mapa.values()].flat())].sort();
  opciones(fTramo, tramos, "Todos");

  const fEstado = $<HTMLSelectElement>("f-estado").value;
  const buscar = $<HTMLInputElement>("f-buscar").value.trim().toLowerCase();
  const visibles = ordenarBandeja(juntas).filter(
    (j) =>
      (!fObra.value || j.obra === fObra.value) &&
      (!fTramo.value || j.tramo === fTramo.value) &&
      (!fEstado || estado(j) === fEstado) &&
      (!buscar || [j.numero, j.soldador, j.progresiva, j.tipoUnion].some((v) => v.toLowerCase().includes(buscar))),
  );

  $("bandeja-vacia").hidden = juntas.length > 0;
  $("filtros").hidden = juntas.length === 0;
  $("tabla-bandeja").hidden = juntas.length === 0;

  const cuenta = (e: string) => juntas.filter((j) => estado(j) === e).length;
  $("resumen-bandeja").innerHTML = juntas.length
    ? [
        `<span>${juntas.length} junta${juntas.length > 1 ? "s" : ""}</span>`,
        `<span class="est-para_revisar">${cuenta("para_revisar")} para revisar</span>`,
        `<span class="est-lista">${cuenta("lista")} ${cuenta("lista") === 1 ? "lista" : "listas"} para decidir</span>`,
        `<span class="est-decidida">${cuenta("decidida")} ${cuenta("decidida") === 1 ? "decidida" : "decididas"}</span>`,
      ].join("")
    : "";

  const tbody = $("tabla-bandeja").querySelector("tbody")!;
  tbody.innerHTML = "";
  for (const j of visibles) {
    const g = RIESGO[grupoRiesgo(j)];
    const tr = document.createElement("tr");
    tr.tabIndex = 0;
    tr.dataset.id = j.id;
    tr.className = `riesgo-${g.clase}`;
    tr.innerHTML = `
      <td><span class="riesgo ${g.clase}">${g.texto}</span></td>
      <td><strong>${esc(j.numero)}</strong>${j.progresiva ? `<br><small class="muted">Prog. ${esc(j.progresiva)}</small>` : ""}${j.ejemplo ? ` <small class="tag">ejemplo</small>` : ""}</td>
      <td>${esc(j.obra)}<br><small class="muted">${esc(j.tramo)}</small></td>
      <td>${esc(j.tipoUnion || "—")}</td>
      <td>${SLOTS.filter((s) => j.imagenes[s]).map((s) => `<span class="tag">${SLOT_INFO[s].corto}</span>`).join(" ")}</td>
      <td>${queVio(j)}</td>
      <td>${estadoHTML(j)}</td>`;
    tr.onclick = () => (location.hash = `#/junta/${j.id}`);
    tr.onkeydown = (e) => e.key === "Enter" && tr.click();
    tbody.append(tr);
  }
  if (juntas.length && !visibles.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="muted center">Ninguna junta coincide con los filtros.</td></tr>`;
  }
}

async function ejemplo() {
  try {
    const n = await cargarEjemplo(juntas);
    toast(n ? `Se cargaron ${n} juntas de ejemplo. La IA las está analizando.` : "La obra de ejemplo ya estaba cargada.");
    await renderBandeja();
    analizarPendientes();
  } catch (error) {
    toast((error as Error).message);
  }
}

export function iniciarBandeja() {
  for (const id of ["f-obra", "f-tramo", "f-estado"]) $(id).onchange = () => renderBandeja();
  $("f-buscar").oninput = () => renderBandeja();
  $("btn-ejemplo").onclick = ejemplo;
  $("btn-ejemplo-2").onclick = ejemplo;
  $("btn-exportar").onclick = async () => {
    const blob = await exportar();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `revision-soldaduras-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  };
  $<HTMLInputElement>("input-importar").onchange = async (e) => {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;
    try {
      const n = await importar(file);
      toast(`Se importaron ${n} juntas.`);
      await renderBandeja();
      analizarPendientes();
    } catch (error) {
      toast(`No pude importar: ${(error as Error).message}`);
    }
  };
}
