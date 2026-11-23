/**
 * Pruebas gemelas: la versión web tiene que dar lo mismo que la versión Python.
 * Los casos se generan con scripts/generate_web_fixtures.py a partir del código Python.
 */
import { describe, expect, it } from "vitest";
import cases from "./fixtures/core_cases.json";
import { classify, decode, dropNested, merge, toPlate, verdict, windows, type Box, type Window } from "../src/core";

// float32 de Python vs float64 de JS: se compara con tolerancia
const close = (a: Box[], b: Box[]) => {
  expect(a.length).toBe(b.length);
  a.forEach((x, i) => {
    expect(x.label).toBe(b[i].label);
    for (const k of ["xMin", "yMin", "xMax", "yMax"] as const) expect(x[k]).toBeCloseTo(b[i][k], 3);
    if (b[i].score === null) expect(x.score).toBeNull();
    else expect(x.score!).toBeCloseTo(b[i].score!, 5);
  });
};

describe("igual que Python", () => {
  it.each(cases.windows)("ventanas de $w × $h", ({ w, h, out }) => {
    expect(windows(w, h)).toEqual(out);
  });

  it.each(cases.merge.map((c, i) => ({ ...c, i })))("une duplicados (caso $i)", (c) => {
    close(merge(c.in as Box[]), c.out as Box[]);
  });

  it.each(cases.decode.map((c, i) => ({ ...c, i })))("decodifica la salida del modelo (caso $i)", (c) => {
    const out = decode(c.logits, c.predBoxes, 3, c.size as [number, number], ["Good Weld", "Bad Weld", "Defect"], c.threshold);
    close(out, c.out as Box[]);
  });

  it.each(cases.review.map((c, i) => ({ ...c, i })))("niveles y resumen (caso $i)", (c) => {
    const kept = dropNested(c.in as Box[]);
    close(kept, c.nested as Box[]);
    const findings = classify(kept, 0.5);
    expect(findings.map((f) => [f.number, f.level])).toEqual(c.findings.map((f) => [f.number, f.level]));
    close(findings.map((f) => f.box), c.findings.map((f) => f.box) as Box[]);
    expect(verdict(findings)).toBe(c.verdict);
  });

  it.each(cases.to_plate.map((c, i) => ({ ...c, i })))("ventana → placa (caso $i)", (c) => {
    close(toPlate(c.in as Box[], c.window as Window), c.out as Box[]);
  });
});

describe("casos borde", () => {
  it("rechaza superposición inválida y tamaño cero", () => {
    expect(() => windows(100, 100, 1)).toThrow();
    expect(() => windows(0, 100)).toThrow();
  });
  it("rechaza cantidad de clases distinta a las etiquetas", () => {
    expect(() => decode([0, 0], [0.5, 0.5, 0.1, 0.1], 2, [10, 10], ["a"], 0.5)).toThrow();
  });
  it("cordón bueno nunca es defecto", () => {
    const [f] = classify([{ xMin: 0, yMin: 0, xMax: 10, yMax: 10, label: "Good Weld", score: 0.99 }], 0.5);
    expect(f.level).toBe("bien");
  });
});

import { resizeRGB } from "../src/resize";

describe("redimensionado igual que Pillow", () => {
  it.each(cases.resize.map((c, i) => ({ ...c, i })))("$w×$h → $outW×$outH (caso $i)", (c) => {
    const out = resizeRGB(Uint8Array.from(c.rgba), c.w, c.h, c.outW, c.outH);
    expect(Array.from(out)).toEqual(c.out);
  });
});
