/**
 * Visor tipo negatoscopio: zoom con la rueda (hacia el puntero), arrastre, brillo, contraste,
 * invertir y los hallazgos encima. Los textos se dibujan en tamaño de pantalla, así se leen
 * igual con cualquier zoom.
 */
import type { Finding } from "./core";
import { displayName } from "./labels";

const COLORS = { defecto: "#dc2626", revisar: "#eab308", bien: "#16a34a", cordonMalo: "#f97316" };

export interface ViewSettings {
  brightness: number; // 1 = normal
  contrast: number; // 1 = normal
  invert: boolean;
  showGood: boolean;
}

export class Viewer {
  private ctx: CanvasRenderingContext2D;
  private image: (CanvasImageSource & { width: number; height: number }) | null = null;
  private findings: Finding[] = [];
  private scale = 1;
  private offset = { x: 0, y: 0 };
  private drag: { x: number; y: number } | null = null;
  selected: number | null = null;
  settings: ViewSettings = { brightness: 1, contrast: 1, invert: false, showGood: true };
  onSelect?: (n: number | null) => void;

  constructor(private canvas: HTMLCanvasElement) {
    this.ctx = canvas.getContext("2d")!;
    new ResizeObserver(() => this.resize()).observe(canvas);
    canvas.addEventListener("wheel", (e) => this.onWheel(e), { passive: false });
    canvas.addEventListener("pointerdown", (e) => this.onDown(e));
    canvas.addEventListener("pointermove", (e) => this.onMove(e));
    canvas.addEventListener("pointerup", (e) => this.onUp(e));
    canvas.addEventListener("dblclick", () => this.fit());
  }

  setImage(image: CanvasImageSource & { width: number; height: number }) {
    this.image = image;
    this.findings = [];
    this.selected = null;
    this.fit();
  }

  setFindings(findings: Finding[]) {
    this.findings = findings;
    this.draw();
  }

  update(settings: Partial<ViewSettings>) {
    Object.assign(this.settings, settings);
    this.draw();
  }

  /** Imagen entera a la vista. */
  fit() {
    if (!this.image) return this.draw();
    const { width, height } = this.canvas.getBoundingClientRect();
    this.scale = Math.min(width / this.image.width, height / this.image.height) * 0.95;
    this.offset = {
      x: (width - this.image.width * this.scale) / 2,
      y: (height - this.image.height * this.scale) / 2,
    };
    this.draw();
  }

  zoomBy(factor: number, cx?: number, cy?: number) {
    const rect = this.canvas.getBoundingClientRect();
    const px = cx ?? rect.width / 2;
    const py = cy ?? rect.height / 2;
    const next = Math.min(Math.max(this.scale * factor, 0.05), 40);
    const k = next / this.scale;
    this.offset = { x: px - (px - this.offset.x) * k, y: py - (py - this.offset.y) * k };
    this.scale = next;
    this.draw();
  }

  /** Centra y acerca un hallazgo. */
  focus(number: number) {
    const f = this.findings.find((x) => x.number === number);
    if (!f) return;
    const rect = this.canvas.getBoundingClientRect();
    const b = f.box;
    const w = Math.max(b.xMax - b.xMin, 1);
    const h = Math.max(b.yMax - b.yMin, 1);
    this.scale = Math.min(Math.min(rect.width / w, rect.height / h) * 0.5, 40);
    this.offset = {
      x: rect.width / 2 - ((b.xMin + b.xMax) / 2) * this.scale,
      y: rect.height / 2 - ((b.yMin + b.yMax) / 2) * this.scale,
    };
    this.selected = number;
    this.draw();
  }

  get zoom() {
    return this.scale;
  }

  private resize() {
    const dpr = window.devicePixelRatio || 1;
    const { width, height } = this.canvas.getBoundingClientRect();
    this.canvas.width = Math.round(width * dpr);
    this.canvas.height = Math.round(height * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.fit();
  }

  private onWheel(e: WheelEvent) {
    e.preventDefault();
    const rect = this.canvas.getBoundingClientRect();
    this.zoomBy(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX - rect.left, e.clientY - rect.top);
  }

  private onDown(e: PointerEvent) {
    this.canvas.setPointerCapture(e.pointerId);
    this.drag = { x: e.clientX, y: e.clientY };
    this.canvas.style.cursor = "grabbing";
  }

  private onMove(e: PointerEvent) {
    if (!this.drag) return;
    this.offset.x += e.clientX - this.drag.x;
    this.offset.y += e.clientY - this.drag.y;
    this.drag = { x: e.clientX, y: e.clientY };
    this.draw();
  }

  private onUp(e: PointerEvent) {
    const moved = this.drag && Math.hypot(e.clientX - this.drag.x, e.clientY - this.drag.y) > 0;
    this.drag = null;
    this.canvas.style.cursor = "grab";
    if (moved) return;
    // Clic sin arrastrar: seleccionar el hallazgo más chico bajo el puntero
    const rect = this.canvas.getBoundingClientRect();
    const ix = (e.clientX - rect.left - this.offset.x) / this.scale;
    const iy = (e.clientY - rect.top - this.offset.y) / this.scale;
    const hit = this.visible()
      .filter((f) => ix >= f.box.xMin && ix <= f.box.xMax && iy >= f.box.yMin && iy <= f.box.yMax)
      .sort((a, b) => area(a) - area(b))[0];
    this.selected = hit ? hit.number : null;
    this.onSelect?.(this.selected);
    this.draw();
  }

  private visible() {
    return this.findings.filter((f) => this.settings.showGood || f.level !== "bien");
  }

  draw() {
    const { ctx } = this;
    const { width, height } = this.canvas.getBoundingClientRect();
    ctx.save();
    ctx.fillStyle = "#0b0f14";
    ctx.fillRect(0, 0, width, height);
    if (!this.image) {
      ctx.restore();
      return;
    }
    const s = this.settings;
    ctx.filter = `brightness(${s.brightness}) contrast(${s.contrast})${s.invert ? " invert(1)" : ""}`;
    ctx.imageSmoothingEnabled = this.scale < 3; // con mucho zoom se ven los píxeles reales
    ctx.drawImage(this.image, this.offset.x, this.offset.y, this.image.width * this.scale, this.image.height * this.scale);
    ctx.filter = "none";

    // del menos importante al más importante: el rojo queda arriba
    for (const f of [...this.visible()].reverse()) this.drawFinding(f);
    ctx.restore();
  }

  private drawFinding(f: Finding) {
    const { ctx } = this;
    const b = f.box;
    const x = this.offset.x + b.xMin * this.scale;
    const y = this.offset.y + b.yMin * this.scale;
    const w = (b.xMax - b.xMin) * this.scale;
    const h = (b.yMax - b.yMin) * this.scale;
    const color =
      f.level === "defecto" && b.label === "Bad Weld" ? COLORS.cordonMalo : COLORS[f.level];
    const selected = this.selected === f.number;
    ctx.lineWidth = selected ? 3 : f.level === "revisar" ? 1.5 : 2;
    ctx.setLineDash(f.level === "revisar" ? [6, 4] : []);
    ctx.strokeStyle = color;
    ctx.strokeRect(x, y, w, h);
    ctx.setLineDash([]);
    if (selected) {
      ctx.fillStyle = `${color}22`;
      ctx.fillRect(x, y, w, h);
    }
    const tag = `${f.level === "revisar" ? "? " : ""}${f.number} ${displayName(b.label)} ${Math.round((b.score ?? 0) * 100)}%`;
    ctx.font = "600 12px system-ui, sans-serif";
    const tw = ctx.measureText(tag).width + 8;
    const ty = y - 18 < 0 ? y : y - 18;
    ctx.fillStyle = color;
    ctx.fillRect(x, ty, tw, 18);
    ctx.fillStyle = f.level === "revisar" ? "#111" : "#fff";
    ctx.fillText(tag, x + 4, ty + 13);
  }
}

const area = (f: Finding) => (f.box.xMax - f.box.xMin) * (f.box.yMax - f.box.yMin);
