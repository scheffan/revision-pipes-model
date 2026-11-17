"""Genera el notebook de Kaggle de la Etapa 1 (datos).

El repo es privado, así que Kaggle no puede instalar el paquete desde GitHub.
Este script copia dentro del notebook el código de `src/revision_pipes/` que hace falta,
para que haya una sola fuente de verdad: si cambia el módulo, se regenera el notebook.

Uso:
    python scripts/build_kaggle_notebook.py           # escribe el notebook
    python scripts/build_kaggle_notebook.py --check   # falla si está desactualizado (CI)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "revision_pipes"
OUT = ROOT / "notebooks" / "etapa1_datos_kaggle.ipynb"
MODULES = ["annotations.py", "splits.py", "visualize.py"]


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n")}


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": text.strip("\n"),
    }


def module_cell(name: str) -> dict:
    source = (SRC / name).read_text(encoding="utf-8")
    return code(f"%%writefile revision_pipes/{name}\n{source}")


CELLS = [
    md("""
# Etapa 1 · Datos — revisión remota de soldaduras

Este notebook:
1. Baja los datasets (radiografías **SWRD** y fotos de cordones de **Roboflow**).
2. Verifica que solo haya imágenes y etiquetas.
3. Convierte los recuadros a un formato común.
4. Detecta duplicados y copias aumentadas para que no haya fuga de datos.
5. Separa entrenamiento / validación / prueba por grupo.
6. Genera gráficos e imágenes con los recuadros dibujados (rojo = defecto, verde = bien).

**Antes de correr:** *Settings → Internet: On* y el secreto `ROBOFLOW_API_KEY` en *Add-ons → Secrets*.
Después: *Run All*. Los resultados quedan en la pestaña *Output* (`/kaggle/working`).
"""),
    md("## 1. Instalación y código del proyecto"),
    code("""
!pip install -q gdown roboflow imagehash
import os
os.makedirs("revision_pipes", exist_ok=True)
open("revision_pipes/__init__.py", "w").close()
"""),
    *[module_cell(name) for name in MODULES],
    code("""
import json, shutil, zipfile
from collections import Counter
from pathlib import Path

import imagehash
import matplotlib.pyplot as plt
from PIL import Image

from revision_pipes.annotations import AnnotationError, Box, clean, from_coco, from_polygon
from revision_pipes.splits import split_by_group
from revision_pipes.visualize import draw_boxes, summarize

WORK = Path("/kaggle/working")
DATA = Path("/tmp/data")  # los datos no van al Output, solo los resultados
DATA.mkdir(parents=True, exist_ok=True)
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
LABEL_EXT = {".json", ".txt", ".xml", ".csv", ".yaml", ".yml"}
DOC_EXT = {".md", ".pdf", ".docx"}
"""),
    md("## 2. Descarga y verificación de seguridad"),
    code("""
def safe_extract(zip_path: Path, dest: Path) -> None:
    \"\"\"Extrae el zip rechazando rutas que intenten salir de la carpeta destino.\"\"\"
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            target = (dest / member).resolve()
            if not str(target).startswith(str(dest.resolve())):
                raise RuntimeError(f"Ruta sospechosa en el zip: {member}")
        zf.extractall(dest)


def audit(folder: Path) -> Counter:
    \"\"\"Cuenta extensiones y borra todo lo que no sea imagen, etiqueta o documentación.\"\"\"
    found, removed = Counter(), []
    for path in folder.rglob("*"):
        if path.is_file():
            ext = path.suffix.lower()
            found[ext] += 1
            if ext not in IMAGE_EXT | LABEL_EXT | DOC_EXT:
                removed.append(str(path.relative_to(folder)))
                path.unlink()
    print("Extensiones encontradas:", dict(found))
    print("Archivos descartados por seguridad:", removed or "ninguno")
    return found
"""),
    code("""
# SWRD: radiografías de soldaduras de costura.
# Opción A (recomendada): subir SWXD_Data.zip a Kaggle como dataset privado y agregarlo al
#   notebook (Add Input). Kaggle lo monta en /kaggle/input/<nombre>/.
# Opción B: bajarlo del Google Drive oficial. Google limita las descargas de archivos muy
#   pedidos ("Too many users..."): si pasa, usar la opción A o reintentar al día siguiente.
SWRD_DIR = DATA / "swrd"
SWRD_DIR.mkdir(exist_ok=True)
local_zips = [z for z in Path("/kaggle/input").rglob("*.zip") if "SW" in z.name.upper()]
local_dirs = [d for d in Path("/kaggle/input").glob("*") if "swrd" in d.name.lower()]
if local_zips:
    print("Usando el zip subido a Kaggle:", local_zips[0])
    safe_extract(local_zips[0], SWRD_DIR)
elif local_dirs:
    print("Usando la carpeta subida a Kaggle:", local_dirs[0])
    shutil.copytree(local_dirs[0], SWRD_DIR, dirs_exist_ok=True)
else:
    !gdown --folder "https://drive.google.com/drive/folders/1LNUt101wufTBJpRAgrZAU1h-Tfx629wO" -O {SWRD_DIR}
for z in SWRD_DIR.rglob("*.zip"):
    print("Extrayendo", z.name, f"({z.stat().st_size / 1e6:.0f} MB)")
    safe_extract(z, SWRD_DIR)
    z.unlink()
if not any(SWRD_DIR.rglob("*.*")):
    print("⚠️ No se pudo obtener SWRD. Seguimos con las fotos de cordones; ver opción A arriba.")
audit(SWRD_DIR);
"""),
    code("""
# Fotos de cordones (Roboflow): principal CC BY 4.0 y complementario de dominio público
from kaggle_secrets import UserSecretsClient
from roboflow import Roboflow

rf = Roboflow(api_key=UserSecretsClient().get_secret("ROBOFLOW_API_KEY"))
SOURCES = {
    "cordones_ccby": ("computer-vision-5vq1v", "welding_defects-2tvbr"),
    "cordones_dominio_publico": ("computer-vision-pl2fz", "welding-defects-detection-ru1eb"),
}
for name, (workspace, project_id) in SOURCES.items():
    project = rf.workspace(workspace).project(project_id)
    try:
        version = max(int(str(v.version).split("/")[-1]) for v in project.versions())
    except Exception:
        version = 1
    print(name, "→ versión", version)
    project.version(version).download("coco", location=str(DATA / name))
    audit(DATA / name)
"""),
    md("## 3. Exploración de SWRD (formato de etiquetas)"),
    code("""
def tree(folder: Path, depth: int = 3, limit: int = 8) -> None:
    for sub in sorted(p for p in folder.rglob("*") if p.is_dir() and len(p.relative_to(folder).parts) <= depth):
        files = [f for f in sub.iterdir() if f.is_file()]
        print(f"{sub.relative_to(folder)}/  ({len(files)} archivos)", [f.name for f in files[:limit]])

tree(SWRD_DIR)
labels = [p for p in SWRD_DIR.rglob("*") if p.suffix.lower() in LABEL_EXT]
print("Archivos de etiquetas:", len(labels))
for sample in labels[:2]:
    print("\\n---", sample.relative_to(SWRD_DIR))
    print(sample.read_text(encoding="utf-8", errors="replace")[:1500])
"""),
    code("""
def load_labelme(path: Path):
    \"\"\"Lee etiquetas estilo LabelMe (shapes con polígonos). Devuelve (imagen, recuadros).\"\"\"
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if "shapes" not in data:
        return None
    image_name = data.get("imagePath") or path.with_suffix(".png").name
    candidates = [path.parent / Path(image_name).name] + [
        path.with_suffix(ext) for ext in IMAGE_EXT
    ]
    image_path = next((c for c in candidates if c.exists()), None)
    if image_path is None:
        return None
    boxes = []
    for shape in data["shapes"]:
        try:
            boxes.append(from_polygon(shape["points"], shape.get("label", "defecto")))
        except (AnnotationError, KeyError):
            pass
    with Image.open(image_path) as im:
        w, h = im.size
    return image_path, clean(boxes, w, h)


swrd = {}
for path in SWRD_DIR.rglob("*.json"):
    result = load_labelme(path)
    if result:
        swrd[result[0]] = result[1]
print("Radiografías SWRD con etiquetas leídas:", len(swrd))
if not swrd:
    print("⚠️ El formato no es LabelMe: copiá la salida de la celda anterior y pasásela a Claude.")
"""),
    md("## 4. Fotos de cordones: lectura, copias aumentadas y duplicados"),
    code("""
def load_coco_folder(folder: Path) -> dict[Path, list[Box]]:
    result = {}
    for ann_file in folder.rglob("_annotations.coco.json"):
        boxes_by_name = from_coco(json.loads(ann_file.read_text()))
        for file_name, boxes in boxes_by_name.items():
            image_path = ann_file.parent / file_name
            if image_path.exists():
                with Image.open(image_path) as im:
                    result[image_path] = clean(boxes, *im.size)
    return result


def original_name(path: Path) -> str:
    \"\"\"Roboflow nombra las copias 'foto_jpg.rf.<hash>.jpg': el original es lo anterior a '.rf.'.\"\"\"
    return path.name.split(".rf.")[0]


cordones = {}
for name in SOURCES:
    loaded = load_coco_folder(DATA / name)
    originals = {original_name(p) for p in loaded}
    print(f"{name}: {len(loaded)} imágenes, {len(originals)} originales")
    cordones.update({p: (name, b) for p, b in loaded.items()})
"""),
    code("""
# Duplicados por contenido (no por nombre). Se arma un "grupo" por foto distinta:
# 1) las copias aumentadas de Roboflow comparten el nombre original;
# 2) fotos casi idénticas (aunque vengan de otro dataset) tienen hash perceptual parecido.
parent = {}

def find(x):
    parent.setdefault(x, x)
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x

def union(a, b):
    parent[find(a)] = find(b)

paths = sorted(cordones)
for path in paths:
    union(str(path), "orig:" + original_name(path))

import numpy as np
bits = []
for path in paths:
    with Image.open(path) as im:
        bits.append(imagehash.phash(im.convert("L")).hash.flatten())
bits = np.array(bits, dtype=bool)  # una fila de 64 bits por imagen
for i in range(len(paths)):
    distances = np.count_nonzero(bits[i + 1:] != bits[i], axis=1)
    for j in np.nonzero(distances <= 4)[0]:
        union(str(paths[i]), str(paths[i + 1 + j]))

group_of_path = {p: find(str(p)) for p in paths}
n_groups = len(set(group_of_path.values()))
print(f"Imágenes: {len(cordones)} · fotos distintas (grupos): {n_groups}")
"""),
    md("## 5. Análisis exploratorio"),
    code("""
def class_counts(items):
    return Counter(b.label for boxes in items for b in boxes)


swrd_counts = class_counts(swrd.values())
cord_counts = class_counts(b for _, b in cordones.values())
panels = [(c, t) for c, t in [
    (swrd_counts, "Radiografías SWRD: defectos por tipo"),
    (cord_counts, "Fotos de cordones: recuadros por clase"),
] if c]
fig, axes = plt.subplots(1, len(panels), figsize=(6 * len(panels), 4), squeeze=False)
for ax, (counts, title) in zip(axes[0], panels):
    if counts:
        labels, values = zip(*counts.most_common())
        ax.barh(labels, values, color="#2563eb")
        ax.invert_yaxis()
        for i, v in enumerate(values):
            ax.text(v, i, f" {v}", va="center")
    ax.set_title(title)
plt.tight_layout()
plt.savefig(WORK / "eda_clases.png", dpi=150)
plt.show()

summary = {
    "swrd": {"imagenes": len(swrd), "recuadros": sum(swrd_counts.values()), "clases": dict(swrd_counts),
             "sin_defectos": sum(1 for b in swrd.values() if not b)},
    "cordones": {"imagenes": len(cordones), "fotos_distintas": n_groups,
                 "recuadros": sum(cord_counts.values()), "clases": dict(cord_counts)},
}
print(json.dumps(summary, indent=2, ensure_ascii=False))
"""),
    md("## 6. Separación sin fuga de datos"),
    code("""
def placa_de_origen(path: Path) -> str:
    # SWRD aplica recorte por ventana deslizante: los recortes de una placa comparten prefijo.
    # Se agrupa por el nombre sin el sufijo de recorte (_0, _1, ...). Revisar con la salida real.
    stem = path.stem
    return stem.rsplit("_", 1)[0] if stem.rsplit("_", 1)[-1].isdigit() else stem


splits = {
    "swrd": split_by_group(sorted(swrd), placa_de_origen),
    "cordones": split_by_group(sorted(cordones), lambda p: group_of_path[p]),
}
rows = []
for dataset, parts in splits.items():
    for split, paths in parts.items():
        print(f"{dataset:9s} {split:5s}: {len(paths)} imágenes")
        rows += [f"{dataset},{split},{p.relative_to(DATA)}" for p in paths]
(WORK / "splits.csv").write_text("dataset,split,archivo\\n" + "\\n".join(rows), encoding="utf-8")

# Verificación: ningún grupo en dos conjuntos
for dataset, group_fn in [("swrd", placa_de_origen), ("cordones", lambda p: group_of_path[p])]:
    sets = {k: {group_fn(p) for p in v} for k, v in splits[dataset].items()}
    assert not (sets["train"] & sets["val"] or sets["train"] & sets["test"] or sets["val"] & sets["test"])
print("✅ Sin fuga: ningún grupo aparece en dos conjuntos")
summary["splits"] = {d: {k: len(v) for k, v in parts.items()} for d, parts in splits.items()}
(WORK / "resumen_etapa1.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
"""),
    md("## 7. Ejemplos con recuadros (capturas para la bitácora)"),
    code("""
def to_display(im: Image.Image) -> Image.Image:
    \"\"\"Las radiografías de 16 bits se ven negras o blancas si no se normalizan.\"\"\"
    if im.mode in ("I;16", "I;16B", "I", "F"):
        import numpy as np
        a = np.asarray(im, dtype=np.float32)
        lo, hi = np.percentile(a, [1, 99])
        a = np.clip((a - lo) / max(hi - lo, 1e-6), 0, 1)
        return Image.fromarray((a * 255).astype("uint8"))
    return im


def grid(items, title, out_name, n=6):
    items = [(p, b) for p, b in items if b][:n]
    if not items:
        print("Sin ejemplos para", title)
        return
    cols = 3
    rows_n = (len(items) + cols - 1) // cols
    fig, axes = plt.subplots(rows_n, cols, figsize=(15, 5 * rows_n))
    for ax in axes.flat:
        ax.axis("off")
    for ax, (path, boxes) in zip(axes.flat, items):
        with Image.open(path) as im:
            ax.imshow(draw_boxes(to_display(im), boxes))
        counts = ", ".join(f"{k}: {v}" for k, v in summarize(boxes).items())
        ax.set_title(counts, fontsize=10)
    fig.suptitle(title, fontsize=14)
    plt.tight_layout()
    plt.savefig(WORK / out_name, dpi=130)
    plt.show()


grid(sorted(swrd.items(), key=lambda kv: -len(kv[1])), "SWRD: defectos marcados en radiografías",
     "ejemplos_swrd.png")
variados, vistos = [], Counter()
for p, (_, b) in sorted(cordones.items()):
    principal = Counter(x.label for x in b).most_common(1)
    if principal and vistos[principal[0][0]] < 2 and group_of_path[p] not in {group_of_path[q] for q, _ in variados}:
        variados.append((p, b))
        vistos[principal[0][0]] += 1
grid(variados, "Fotos de cordones: rojo = defecto, "
     "ámbar = cordón malo, verde = cordón bueno", "ejemplos_cordones.png")
print("Listo. Descargá de la pestaña Output: eda_clases.png, ejemplos_swrd.png, "
      "ejemplos_cordones.png, resumen_etapa1.json y splits.csv")
"""),
]


def build() -> str:
    notebook = {
        "cells": CELLS,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    return json.dumps(notebook, ensure_ascii=False, indent=1) + "\n"


def main() -> int:
    content = build()
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != content:
            print("El notebook está desactualizado: corré python scripts/build_kaggle_notebook.py")
            return 1
        print("Notebook al día.")
        return 0
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(content, encoding="utf-8")
    print(f"Notebook generado: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
