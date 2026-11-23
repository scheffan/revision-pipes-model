"""Celdas del notebook de Kaggle que calibra el "umbral alto" (rojo o amarillo) de cada detector.

El umbral del modelo decide qué se muestra; el umbral alto solo decide el color: rojo cuando el
modelo suele acertar, amarillo punteado ("revisar") cuando duda. Se elige en validación, con
los modelos ONNX que usa la app y el mismo procesamiento, y se comprueba en prueba.
Las usa scripts/build_kaggle_notebook.py. El código de las celdas va como texto.
"""

from etapa2_cells import CONFIG, DOWNLOAD, IMPORTS, LOAD_SPLIT

INTRO = """
# Calibración del rojo y el amarillo — revisión remota de soldaduras

La app muestra todo lo que supera el umbral del modelo (elegido para no perder defectos). Entre
eso, **rojo** quiere decir "el modelo suele acertar" y **amarillo punteado** "duda, conviene
mirarlo". Este notebook elige el corte entre los dos:

1. Baja los datasets y arma los **mismos conjuntos** que el entrenamiento (misma semilla).
2. Corre los modelos **ONNX de la app** sobre validación, con el mismo procesamiento que la web.
3. Para cada corte posible mide la **precisión** (qué parte de los recuadros marca un defecto
   real) y elige el corte más bajo con al menos 80 % de precisión.
4. Comprueba ese corte en **prueba** (imágenes que no se usaron para elegirlo).

**Antes de correr:** *Internet: On*, el secreto `ROBOFLOW_API_KEY` y como entradas (*Add Input →
Notebooks*) las salidas de los notebooks de radiografías y de cordones, que tienen los `.onnx`.
No hace falta GPU.
"""

CALIBRATE = """
import zipfile
from revision_pipes.inference import Detector
from revision_pipes.review import drop_nested

TARGET_PRECISION = 0.80     # en rojo, al menos 8 de cada 10 recuadros tienen que ser defectos reales
MIN_RED = 15                # cantidad mínima de recuadros en rojo para confiar en la precisión
IOU_MATCH = 0.5
UMBRAL_MODELO = {"radiografias": 0.5, "cordones": 0.15}[MODULO]


def find_model(name: str) -> Path:
    hits = sorted(Path("/kaggle/input").rglob(name))
    if hits:
        return hits[0]
    for z in sorted(Path("/kaggle/input").rglob("*.zip")):
        with zipfile.ZipFile(z) as zf:
            inside = [n for n in zf.namelist() if n.endswith(name)]
            if inside:
                zf.extract(inside[0], "/tmp/modelos")
                return Path("/tmp/modelos") / inside[0]
    raise FileNotFoundError(f"No encuentro {name}: agregá la salida del notebook como entrada.")


onnx_path = find_model(f"modelo_{MODULO}.onnx")
print("Modelo:", onnx_path)
detector = Detector.from_file(str(onnx_path), LABELS, UMBRAL_MODELO)


def run(split: str) -> dict:
    out = {}
    for i, p in enumerate(splits[split]):
        with Image.open(p) as im:
            # igual que la app: ventanas, unión de duplicados y sin recuadros encimados
            out[p] = drop_nested(detector.predict(im.convert("RGB")))
        if i % 100 == 0:
            print(f"  {split}: {i}/{len(splits[split])}")
    return out


def scored(preds: dict) -> list:
    \"\"\"(puntaje, acierta con cualquier defecto, acierta con el mismo tipo) por recuadro de defecto.\"\"\"
    rows = []
    for p, boxes in preds.items():
        truth = defects(items[p])
        for b in defects(boxes):
            any_hit = any(iou(b, t) >= IOU_MATCH for t in truth)
            same_hit = any(iou(b, t) >= IOU_MATCH and t.label == b.label for t in truth)
            rows.append((b.score, any_hit, same_hit))
    return sorted(rows, reverse=True)


def curve(rows: list) -> list:
    points, hits, same = [], 0, 0
    total_hits = sum(r[1] for r in rows) or 1
    for n, (score, any_hit, same_hit) in enumerate(rows, start=1):
        hits += any_hit
        same += same_hit
        points.append({"umbral": round(score, 4), "rojos": n, "precision": hits / n,
                       "precision_mismo_tipo": same / n, "aciertos_en_rojo": hits / total_hits})
    return points


def summary(rows: list, threshold: float) -> dict:
    red = [r for r in rows if r[0] >= threshold]
    yellow = [r for r in rows if r[0] < threshold]
    pct = lambda xs, k: round(sum(x[k] for x in xs) / len(xs), 3) if xs else None
    return {"rojos": len(red), "precision_rojos": pct(red, 1), "precision_rojos_mismo_tipo": pct(red, 2),
            "amarillos": len(yellow), "precision_amarillos": pct(yellow, 1),
            "defectos_reales_en_rojo": round(sum(r[1] for r in red) / max(1, sum(r[1] for r in rows)), 3)}


print("Validación…")
val_rows = scored(run("val"))
points = curve(val_rows)
ok = [pt for pt in points if pt["rojos"] >= MIN_RED and pt["precision"] >= TARGET_PRECISION]
# El corte más bajo que sigue cumpliendo (el último en orden de puntaje descendente)
chosen = ok[-1]["umbral"] if ok else 1.0
chosen = max(chosen, UMBRAL_MODELO)
print(f"Umbral alto elegido: {chosen} ({'cumple' if ok else 'ningún corte llega al 80 %: todo amarillo'})")

print("Prueba…")
test_rows = scored(run("test"))
result = {
    "modulo": MODULO,
    "umbral_modelo": UMBRAL_MODELO,
    "umbral_alto": chosen,
    "objetivo_precision": TARGET_PRECISION,
    "validacion": summary(val_rows, chosen),
    "prueba": summary(test_rows, chosen),
    "curva_validacion": points[::max(1, len(points) // 60)],
}
print(json.dumps({k: v for k, v in result.items() if k != "curva_validacion"}, indent=2, ensure_ascii=False))
(WORK / f"calibracion_{MODULO}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))

fig, ax = plt.subplots(figsize=(7, 4))
ax.plot([pt["umbral"] for pt in points], [pt["precision"] for pt in points], label="precisión de los rojos")
ax.plot([pt["umbral"] for pt in points], [pt["aciertos_en_rojo"] for pt in points],
        label="defectos reales que quedan en rojo")
ax.axvline(chosen, color="red", ls="--", label=f"corte elegido {chosen:.2f}")
ax.axhline(TARGET_PRECISION, color="gray", ls=":")
ax.set_xlabel("puntaje del modelo"); ax.set_ylim(0, 1.02); ax.legend(); ax.set_title(f"Calibración · {MODULO}")
plt.tight_layout(); plt.savefig(WORK / f"calibracion_{MODULO}.png", dpi=120); plt.show()
"""


def cells_calibracion(md, code, module_cell, modules):
    cells = [
        md(INTRO),
        code("!pip install -q roboflow imagehash onnxruntime\n"
             "import os\nos.makedirs('revision_pipes', exist_ok=True)\n"
             "open('revision_pipes/__init__.py', 'w').close()"),
        *[module_cell(name) for name in modules],
    ]
    for modulo in ("radiografias", "cordones"):
        cells += [
            md(f"## {modulo.capitalize()}"),
            code(CONFIG.replace('MODULO = "radiografias"', f'MODULO = "{modulo}"')),
            code(IMPORTS),
            code(DOWNLOAD),
            code(LOAD_SPLIT),
            code(CALIBRATE),
        ]
    cells.append(code('print("Listo. Pasale a Claude los calibracion_*.json de Output.")'))
    return cells
