/**
 * Informe de una junta, listo para "Guardar como PDF" desde la ventana de impresión del navegador.
 * Lleva los datos de la junta, cada imagen con sus marcas, los hallazgos con lo que decidió el
 * inspector, la decisión y el historial.
 */
import { estado, ESTADOS, labelFinal, necesitaRevision, RESULTADOS, SLOTS, type Evento, type Junta } from "../juntas";
import { displayName } from "../labels";
import { SLOT_INFO } from "../pipeline";
import { imagenMarcada } from "../viewer";
import { bitmapDe } from "./revision";
import { esc, fecha, LEVEL_TEXT } from "./ui";

const REV = { pendiente: "Sin revisar", aceptado: "Aceptado", descartado: "Descartado (falsa alarma)" };

export async function imprimirInforme(j: Junta, eventos: Evento[]) {
  const el = document.getElementById("informe")!;
  const datos: [string, string][] = [
    ["Obra", j.obra],
    ["Tramo", j.tramo],
    ["Junta", j.numero],
    ["Progresiva", j.progresiva],
    ["Tipo de unión", j.tipoUnion],
    ["Material", j.material],
    ["Diámetro", j.diametro],
    ["Espesor", j.espesor],
    ["Proceso", j.proceso],
    ["Soldador", j.soldador],
  ];
  const d = j.decision;
  let html = `
    <header>
      <div><h1>Informe de revisión de soldadura</h1><p>Junta ${esc(j.numero)} · ${esc(j.obra)} · ${esc(j.tramo)}</p></div>
      <div class="meta">Emitido: ${fecha(new Date().toISOString())}</div>
    </header>
    <section class="resultado ${d ? `res-${d.resultado}` : ""}">
      ${
        d
          ? `<strong>${RESULTADOS[d.resultado]}</strong> · Inspector: ${esc(d.inspector)} · ${fecha(d.fecha)} · Norma: ${esc(d.norma)}${d.nota ? `<p>${esc(d.nota)}</p>` : ""}`
          : `<strong>Sin decisión</strong> · Estado: ${ESTADOS[estado(j)]}. Este informe es un borrador.`
      }
    </section>
    <table class="datos">${datos
      .filter(([, v]) => v)
      .map(([k, v]) => `<tr><th>${k}</th><td>${esc(v)}</td></tr>`)
      .join("")}</table>`;

  for (const s of SLOTS) {
    const img = j.imagenes[s];
    if (!img) continue;
    const titulo = SLOT_INFO[s].nombre.charAt(0).toUpperCase() + SLOT_INFO[s].nombre.slice(1);
    const hallazgos = img.analisis?.hallazgos ?? [];
    const bitmap = await bitmapDe(img.imagenId);
    const src = bitmap ? imagenMarcada(bitmap, hallazgos.filter((h) => h.revision !== "descartado")).toDataURL("image/png") : "";
    const filas = hallazgos
      .filter((h) => necesitaRevision(h))
      .map(
        (h) => `<tr class="rev-${h.revision}"><td>${h.number}</td><td>${esc(displayName(labelFinal(h)))}${
          h.labelInspector ? ` <small>(IA: ${esc(displayName(h.box.label))})</small>` : ""
        }</td><td>${LEVEL_TEXT[h.level]} · ${Math.round((h.box.score ?? 0) * 100)} %</td><td>${REV[h.revision]}</td></tr>`,
      )
      .join("");
    html += `
      <section class="imagen">
        <h2>${titulo} <small>${esc(img.nombre)}</small></h2>
        ${src ? `<img src="${src}" alt="${titulo} con hallazgos marcados" />` : `<p>No se encontró la imagen.</p>`}
        ${
          img.analisis
            ? filas
              ? `<table class="hallazgos"><thead><tr><th>N.º</th><th>Tipo</th><th>IA</th><th>Inspector</th></tr></thead><tbody>${filas}</tbody></table>`
              : `<p>La IA no marcó posibles defectos.</p>`
            : `<p>Sin analizar.</p>`
        }
        ${img.analisis ? `<p class="small">Análisis automático: ${fecha(img.analisis.fecha)} · modelo ${esc(img.analisis.version || "–")} · umbral alto ${img.analisis.umbral}</p>` : ""}
      </section>`;
  }

  html += `
    <section class="hist">
      <h2>Historial</h2>
      <ol>${eventos.map((e) => `<li>${fecha(e.fecha)} · <strong>${esc(e.quien)}</strong> ${esc(e.detalle)}</li>`).join("")}</ol>
    </section>
    <footer>La detección automática solo prioriza. La aceptación o el rechazo los decide el inspector según la norma indicada. Generado con una demo de portfolio, no con un sistema certificado.</footer>`;

  el.innerHTML = html;
  await Promise.all([...el.querySelectorAll("img")].map((i) => i.decode().catch(() => undefined)));
  const titulo = document.title;
  document.title = `Informe ${j.numero} - ${j.obra}`; // nombre sugerido del PDF
  window.print();
  document.title = titulo;
}
