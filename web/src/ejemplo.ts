/**
 * Obra de ejemplo para quien entra a la demo sin imágenes propias.
 * Imágenes: de los datasets de Roboflow usados para entrenar (CC BY 4.0), ver "Acerca de".
 */
import type { DatosJunta, Junta, Slot } from "./juntas";
import { ahora, guardarImagen, guardarJunta, nuevoId, registrar } from "./store";

const OBRA = "Gasoducto de ejemplo";
const BASE = { material: "API 5L X70", diametro: '24"', espesor: "12,7 mm", proceso: "SMAW" };

const JUNTAS: (Omit<DatosJunta, "obra" | keyof typeof BASE> & { imagenes: Partial<Record<Slot, string>> })[] = [
  {
    tramo: "Tramo 3 · Km 12–18",
    numero: "J-0142",
    progresiva: "12+340",
    tipoUnion: "Caño–caño",
    soldador: "S-07",
    imagenes: { radiografia: "radiografia_1.png", foto: "foto_cordon_1.jpg" },
  },
  {
    tramo: "Tramo 3 · Km 12–18",
    numero: "J-0143",
    progresiva: "12+352",
    tipoUnion: "Caño–codo",
    soldador: "S-07",
    imagenes: { radiografia: "radiografia_2.png" },
  },
  {
    tramo: "Tramo 4 · Km 18–24",
    numero: "J-0201",
    progresiva: "18+012",
    tipoUnion: "Caño–caño",
    soldador: "S-12",
    imagenes: { foto: "foto_cordon_2.jpg" },
  },
];

export async function cargarEjemplo(existentes: Junta[]): Promise<number> {
  let n = 0;
  for (const def of JUNTAS) {
    if (existentes.some((j) => j.obra === OBRA && j.numero === def.numero)) continue;
    const imagenes: Junta["imagenes"] = {};
    for (const [slot, archivo] of Object.entries(def.imagenes) as [Slot, string][]) {
      const resp = await fetch(`${import.meta.env.BASE_URL}ejemplos/${archivo}`);
      if (!resp.ok) throw new Error(`No pude bajar la imagen de ejemplo ${archivo}.`);
      imagenes[slot] = { imagenId: await guardarImagen(await resp.blob()), nombre: archivo };
    }
    const { imagenes: _, ...datos } = def;
    const junta: Junta = { ...datos, ...BASE, obra: OBRA, id: nuevoId(), creada: ahora(), imagenes, ejemplo: true };
    await guardarJunta(junta);
    await registrar({ juntaId: junta.id, accion: "Carga", detalle: "cargó la junta de ejemplo" });
    n++;
  }
  return n;
}
