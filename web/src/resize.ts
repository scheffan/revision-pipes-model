/**
 * Redimensionado idéntico al de Pillow (Image.resize con BILINEAR), píxel por píxel.
 *
 * El modelo se entrenó con imágenes achicadas por Pillow. El navegador achica distinto (sin el
 * filtro antialias de Pillow), y esa diferencia alcanza para que hallazgos cerca del umbral
 * aparezcan o desaparezcan. Por eso se replica el algoritmo de Pillow (libImaging/Resample.c):
 * dos pasadas (horizontal y vertical) con filtro triangular, pesos en punto fijo y redondeo a
 * 8 bits entre pasadas. tests/resize.test.ts lo compara contra Pillow.
 */

const PRECISION_BITS = 32 - 8 - 2;

interface Coeffs {
  bounds: Int32Array; // por cada píxel de salida: inicio y cantidad de píxeles de entrada
  kk: Int32Array; // pesos en punto fijo, ksize por píxel de salida
  ksize: number;
}

function bilinear(x: number): number {
  x = Math.abs(x);
  return x < 1 ? 1 - x : 0;
}

function precompute(inSize: number, outSize: number): Coeffs {
  const scale = inSize / outSize;
  const filterscale = Math.max(scale, 1);
  const support = 1 * filterscale;
  const ksize = Math.ceil(support) * 2 + 1;
  const bounds = new Int32Array(outSize * 2);
  const kk = new Int32Array(outSize * ksize);
  const k = new Float64Array(ksize);
  for (let xx = 0; xx < outSize; xx++) {
    const center = (xx + 0.5) * scale;
    const ss = 1 / filterscale;
    let xmin = Math.trunc(center - support + 0.5);
    if (xmin < 0) xmin = 0;
    let xmax = Math.trunc(center + support + 0.5);
    if (xmax > inSize) xmax = inSize;
    xmax -= xmin;
    let ww = 0;
    for (let x = 0; x < xmax; x++) {
      const w = bilinear((x + xmin - center + 0.5) * ss);
      k[x] = w;
      ww += w;
    }
    for (let x = 0; x < ksize; x++) {
      const w = x < xmax && ww !== 0 ? k[x] / ww : 0;
      // igual que Pillow: redondeo hacia afuera de cero
      kk[xx * ksize + x] = w < 0 ? Math.trunc(-0.5 + w * (1 << PRECISION_BITS)) : Math.trunc(0.5 + w * (1 << PRECISION_BITS));
    }
    bounds[xx * 2] = xmin;
    bounds[xx * 2 + 1] = xmax;
  }
  return { bounds, kk, ksize };
}

const clip8 = (v: number) => {
  const r = Math.floor(v / (1 << PRECISION_BITS)); // >> con números grandes sin desbordar
  return r < 0 ? 0 : r > 255 ? 255 : r;
};

/** RGBA (w × h) → RGB (outW × outH) en bytes, como Pillow. */
export function resizeRGB(
  rgba: Uint8ClampedArray | Uint8Array,
  w: number,
  h: number,
  outW: number,
  outH: number,
): Uint8Array {
  const horiz = precompute(w, outW);
  const vert = precompute(h, outH);
  // Pasada horizontal: solo las filas que va a usar la vertical
  const ymin = vert.bounds[0];
  const ymax = vert.bounds[(outH - 1) * 2] + vert.bounds[(outH - 1) * 2 + 1];
  const rows = ymax - ymin;
  const tmp = new Uint8Array(rows * outW * 3);
  const half = 1 << (PRECISION_BITS - 1);
  for (let y = 0; y < rows; y++) {
    const src = (y + ymin) * w * 4;
    for (let xx = 0; xx < outW; xx++) {
      const xmin = horiz.bounds[xx * 2];
      const n = horiz.bounds[xx * 2 + 1];
      const kb = xx * horiz.ksize;
      let r = half, g = half, b = half;
      for (let x = 0; x < n; x++) {
        const p = src + (x + xmin) * 4;
        const kv = horiz.kk[kb + x];
        r += rgba[p] * kv;
        g += rgba[p + 1] * kv;
        b += rgba[p + 2] * kv;
      }
      const o = (y * outW + xx) * 3;
      tmp[o] = clip8(r);
      tmp[o + 1] = clip8(g);
      tmp[o + 2] = clip8(b);
    }
  }
  // Pasada vertical
  const out = new Uint8Array(outW * outH * 3);
  for (let yy = 0; yy < outH; yy++) {
    const y0 = vert.bounds[yy * 2] - ymin;
    const n = vert.bounds[yy * 2 + 1];
    const kb = yy * vert.ksize;
    for (let xx = 0; xx < outW; xx++) {
      let r = half, g = half, b = half;
      for (let y = 0; y < n; y++) {
        const p = ((y + y0) * outW + xx) * 3;
        const kv = vert.kk[kb + y];
        r += tmp[p] * kv;
        g += tmp[p + 1] * kv;
        b += tmp[p + 2] * kv;
      }
      const o = (yy * outW + xx) * 3;
      out[o] = clip8(r);
      out[o + 1] = clip8(g);
      out[o + 2] = clip8(b);
    }
  }
  return out;
}
