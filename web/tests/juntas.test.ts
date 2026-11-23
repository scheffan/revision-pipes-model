import { describe, expect, it } from "vitest";
import type { Box, Level } from "../src/core";
import {
  confirmados,
  decidir,
  estado,
  grupoRiesgo,
  obrasYTramos,
  ordenarBandeja,
  pendientes,
  puedeDecidir,
  reabrir,
  revisarHallazgo,
  validarJunta,
  type DatosJunta,
  type Hallazgo,
  type Junta,
} from "../src/juntas";

const box = (label: string, score: number): Box => ({ xMin: 0, yMin: 0, xMax: 10, yMax: 10, label, score });
const h = (number: number, level: Level, score: number, label = "porosidad"): Hallazgo => ({
  number,
  box: box(level === "bien" ? "Good Weld" : label, score),
  level,
  revision: "pendiente",
});
const datos = (numero: string, obra = "Gasoducto Norte", tramo = "Tramo 3"): DatosJunta => ({
  obra,
  tramo,
  numero,
  progresiva: "",
  tipoUnion: "Caño–caño",
  material: "",
  diametro: "",
  espesor: "",
  proceso: "",
  soldador: "",
});
function junta(numero: string, rx?: Hallazgo[] | null, foto?: Hallazgo[] | null): Junta {
  const img = (hs: Hallazgo[] | null | undefined) =>
    hs === undefined ? undefined : { imagenId: numero, nombre: "x", analisis: hs === null ? undefined : { fecha: "", version: "v", umbral: 0.5, hallazgos: hs } };
  return { ...datos(numero), id: numero, creada: "", imagenes: { radiografia: img(rx), foto: img(foto) } };
}
const DEC = { resultado: "aprobada" as const, nota: "", inspector: "Ana", norma: "API 1104", fecha: "2026-11-22" };

describe("estado", () => {
  it("sin analizar si falta analizar una imagen", () => {
    expect(estado(junta("1", null))).toBe("sin_analizar");
    expect(estado(junta("1", [], null))).toBe("sin_analizar");
    expect(estado(junta("1"))).toBe("sin_analizar"); // sin imágenes
  });
  it("para revisar mientras haya hallazgos pendientes; los sanos no cuentan", () => {
    expect(estado(junta("1", [h(1, "defecto", 0.9)]))).toBe("para_revisar");
    expect(estado(junta("1", undefined, [h(1, "bien", 0.9)]))).toBe("lista");
    expect(estado(junta("1", []))).toBe("lista");
  });
});

describe("bandeja", () => {
  it("ordena defectos por confianza, después revisar, sin analizar, sin hallazgos y decididas", () => {
    const decidida = decidir(junta("A", []), DEC);
    const lista = [
      decidida,
      junta("B", []),
      junta("C", null),
      junta("D", [h(1, "revisar", 0.3)]),
      junta("E", [h(1, "defecto", 0.6)]),
      junta("F", undefined, [h(1, "defecto", 0.95, "Bad Weld")]),
    ];
    expect(ordenarBandeja(lista).map((j) => j.numero)).toEqual(["F", "E", "D", "C", "B", "A"]);
    expect(lista.map(grupoRiesgo)).toEqual([4, 3, 2, 1, 0, 0]);
  });
  it("a igual riesgo ordena por número de junta (J-2 antes que J-10)", () => {
    expect(ordenarBandeja([junta("J-10", []), junta("J-2", [])]).map((j) => j.numero)).toEqual(["J-2", "J-10"]);
  });
  it("lo descartado por el inspector deja de subir la junta", () => {
    const j = revisarHallazgo(junta("1", [h(1, "defecto", 0.9)]), "radiografia", 1, "descartar").junta;
    expect(grupoRiesgo(j)).toBe(3);
  });
});

describe("revisión y decisión", () => {
  it("la decisión queda bloqueada hasta revisar todo", () => {
    let j = junta("1", [h(1, "defecto", 0.9), h(2, "revisar", 0.3)], [h(1, "bien", 0.8)]);
    expect(puedeDecidir(j)).toEqual({ ok: false, motivo: "Faltan revisar 2 hallazgos." });
    expect(() => decidir(j, DEC)).toThrow("Faltan revisar");
    j = revisarHallazgo(j, "radiografia", 1, "aceptar").junta;
    j = revisarHallazgo(j, "radiografia", 2, "descartar").junta;
    expect(pendientes(j)).toBe(0);
    expect(puedeDecidir(j).ok).toBe(true);
  });

  it("cambiar el tipo lo acepta con el tipo nuevo y queda en el historial", () => {
    const r = revisarHallazgo(junta("1", [h(1, "defecto", 0.9)]), "radiografia", 1, "cambiar", "fisura");
    expect(r.detalle).toBe("cambió el hallazgo 1 de la radiografía (porosidad → fisura)");
    expect(confirmados(r.junta).map((c) => c.h.labelInspector)).toEqual(["fisura"]);
    const back = revisarHallazgo(r.junta, "radiografia", 1, "deshacer").junta;
    expect(back.imagenes.radiografia!.analisis!.hallazgos[0]).toEqual(h(1, "defecto", 0.9));
  });

  it("no modifica la junta original", () => {
    const j = junta("1", [h(1, "defecto", 0.9)]);
    revisarHallazgo(j, "radiografia", 1, "aceptar");
    expect(j.imagenes.radiografia!.analisis!.hallazgos[0].revision).toBe("pendiente");
  });

  it("reparar o rechazar exige motivo; decidida no se puede revisar hasta reabrir", () => {
    const j = junta("1", []);
    expect(() => decidir(j, { ...DEC, resultado: "reparar" })).toThrow("motivo");
    expect(() => decidir(j, { ...DEC, inspector: " " })).toThrow("inspector");
    const d = decidir(j, { ...DEC, resultado: "reparar", nota: " poro en raíz " });
    expect(d.decision!.nota).toBe("poro en raíz");
    expect(estado(d)).toBe("decidida");
    expect(estado(reabrir(d))).toBe("lista");
    const conHallazgo = decidir(revisarHallazgo(junta("2", [h(1, "defecto", 0.9)]), "radiografia", 1, "aceptar").junta, DEC);
    expect(() => revisarHallazgo(conHallazgo, "radiografia", 1, "descartar")).toThrow("reabrila");
  });
});

describe("carga", () => {
  it("pide obra, tramo, número e imagen", () => {
    expect(Object.keys(validarJunta(datos("", "", ""), [], []))).toEqual(["obra", "tramo", "numero", "imagenes"]);
    expect(validarJunta(datos("J-1"), ["foto"], [])).toEqual({});
  });
  it("no repite número en la misma obra (sí en otra obra, y no se choca consigo misma)", () => {
    const existentes = [junta("J-1")];
    expect(validarJunta(datos("j-1"), ["foto"], existentes).numero).toContain("Ya hay");
    expect(validarJunta(datos("J-1", "Otra obra"), ["foto"], existentes)).toEqual({});
    expect(validarJunta(datos("J-1"), ["foto"], existentes, "J-1")).toEqual({});
  });
  it("lista obras y tramos ordenados", () => {
    const js = [junta("1"), { ...junta("2"), tramo: "Tramo 10" }, { ...junta("3"), obra: "Acueducto" }];
    expect([...obrasYTramos(js)]).toEqual([
      ["Acueducto", ["Tramo 3"]],
      ["Gasoducto Norte", ["Tramo 3", "Tramo 10"]],
    ]);
  });
});
