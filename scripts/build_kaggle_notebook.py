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
MODULES = ["annotations.py", "splits.py", "taxonomy.py", "visualize.py"]


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
1. Baja los datasets de **Roboflow**: radiografías de soldaduras y fotos de cordones.
2. Verifica que solo haya imágenes y etiquetas.
3. Convierte los recuadros a un formato común y unifica los nombres de los defectos.
4. Detecta copias aumentadas y fotos repetidas para que no haya fuga de datos.
5. Separa entrenamiento / validación / prueba por grupo.
6. Genera gráficos e imágenes con los recuadros dibujados (rojo = defecto, verde = bien).

**Antes de correr:** *Settings → Internet: On* y el secreto `ROBOFLOW_API_KEY` en *Add-ons → Secrets*.
Después: *Run All*. Los resultados quedan en la pestaña *Output* (`/kaggle/working`).
"""),
    md("## 1. Instalación y código del proyecto"),
    code("""
!pip install -q roboflow imagehash
import os
os.makedirs("revision_pipes", exist_ok=True)
open("revision_pipes/__init__.py", "w").close()
"""),
    *[module_cell(name) for name in MODULES],
    code("""
import json
from collections import Counter
from pathlib import Path

import imagehash
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from revision_pipes.annotations import Box, clean, from_coco
from revision_pipes.splits import split_by_group
from revision_pipes.taxonomy import normalize_label
from revision_pipes.visualize import draw_boxes, summarize

WORK = Path("/kaggle/working")
DATA = Path("/tmp/data")  # los datos no van al Output, solo los resultados
DATA.mkdir(parents=True, exist_ok=True)
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
LABEL_EXT = {".json", ".txt", ".xml", ".csv", ".yaml", ".yml"}
DOC_EXT = {".md", ".pdf", ".docx"}

# nombre: (workspace, proyecto, versión o None = la última, tipo)
# Las versiones fijas son las que NO tienen aumentaciones (copias rotadas/recortadas).
SOURCES = {
    "rx_weld": ("kunkun-vhmx2", "weld-2z7bw", 1, "radiografias"),
    "rx_weld_data": ("vayun-goel-jlreu", "weld-data-4ln0h", None, "radiografias"),
    "cordones_ccby": ("computer-vision-5vq1v", "welding_defects-2tvbr", 1, "cordones"),
    "cordones_dominio_publico": ("computer-vision-pl2fz", "welding-defects-detection-ru1eb", None, "cordones"),
}
"""),
    md("## 2. Descarga y verificación de seguridad"),
    code("""
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
    print("  Extensiones:", dict(found), "· descartados:", removed or "ninguno")
    return found


from kaggle_secrets import UserSecretsClient
from roboflow import Roboflow

rf = Roboflow(api_key=UserSecretsClient().get_secret("ROBOFLOW_API_KEY"))
for name, (workspace, project_id, version, kind) in SOURCES.items():
    project = rf.workspace(workspace).project(project_id)
    if version is None:
        try:
            version = max(int(str(v.version).split("/")[-1]) for v in project.versions())
        except Exception:
            version = 1
    print(f"{name} ({kind}) → versión {version}")
    project.version(version).download("coco", location=str(DATA / name))
    audit(DATA / name)
"""),
    md("## 3. Lectura, nombres comunes, copias aumentadas y duplicados"),
    code("""
def load_coco_folder(folder: Path, normalize: bool) -> dict:
    result = {}
    for ann_file in folder.rglob("_annotations.coco.json"):
        boxes_by_name = from_coco(json.loads(ann_file.read_text()))
        for file_name, boxes in boxes_by_name.items():
            image_path = ann_file.parent / file_name
            if not image_path.exists():
                continue
            if normalize:
                boxes = [Box(b.x_min, b.y_min, b.x_max, b.y_max, normalize_label(b.label)) for b in boxes]
            with Image.open(image_path) as im:
                result[image_path] = clean(boxes, *im.size)
    return result


def original_name(path: Path) -> str:
    \"\"\"Roboflow nombra las copias 'foto_jpg.rf.<hash>.jpg': el original es lo anterior a '.rf.'.\"\"\"
    return path.name.split(".rf.")[0]


def group_images(paths: list) -> dict:
    \"\"\"Agrupa copias aumentadas (mismo nombre original) y fotos casi idénticas (hash parecido).\"\"\"
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    for path in paths:
        union(str(path), "orig:" + original_name(path))
    bits = []
    for path in paths:
        with Image.open(path) as im:
            bits.append(imagehash.phash(im.convert("L")).hash.flatten())
    bits = np.array(bits, dtype=bool)
    for i in range(len(paths)):
        distances = np.count_nonzero(bits[i + 1:] != bits[i], axis=1)
        for j in np.nonzero(distances <= 4)[0]:
            union(str(paths[i]), str(paths[i + 1 + j]))
    return {p: find(str(p)) for p in paths}


datasets, groups = {}, {}
for name, (_, _, _, kind) in SOURCES.items():
    loaded = load_coco_folder(DATA / name, normalize=(kind == "radiografias"))
    print(f"{name}: {len(loaded)} imágenes, {len({original_name(p) for p in loaded})} originales")
    datasets.setdefault(kind, {}).update(loaded)

for kind, items in datasets.items():
    groups[kind] = group_images(sorted(items))
    print(f"{kind}: {len(items)} imágenes · {len(set(groups[kind].values()))} fotos distintas")
"""),
    md("## 4. Análisis exploratorio"),
    code("""
counts = {kind: Counter(b.label for boxes in items.values() for b in boxes) for kind, items in datasets.items()}
titles = {"radiografias": "Radiografías: defectos por tipo", "cordones": "Fotos de cordones: recuadros por clase"}
fig, axes = plt.subplots(1, len(counts), figsize=(7 * len(counts), 5), squeeze=False)
for ax, (kind, c) in zip(axes[0], counts.items()):
    labels, values = zip(*c.most_common())
    ax.barh(labels, values, color="#2563eb")
    ax.invert_yaxis()
    for i, v in enumerate(values):
        ax.text(v, i, f" {v}", va="center")
    ax.set_title(titles.get(kind, kind))
plt.tight_layout()
plt.savefig(WORK / "eda_clases.png", dpi=150)
plt.show()

summary = {
    kind: {
        "imagenes": len(items),
        "fotos_distintas": len(set(groups[kind].values())),
        "imagenes_sin_recuadros": sum(1 for b in items.values() if not b),
        "recuadros": sum(counts[kind].values()),
        "clases": dict(counts[kind].most_common()),
    }
    for kind, items in datasets.items()
}
print(json.dumps(summary, indent=2, ensure_ascii=False))
"""),
    md("## 5. Separación sin fuga de datos"),
    code("""
rows, summary_splits = [], {}
for kind, items in datasets.items():
    parts = split_by_group(sorted(items), lambda p, k=kind: groups[k][p])
    sets = {k: {groups[kind][p] for p in v} for k, v in parts.items()}
    assert not (sets["train"] & sets["val"] or sets["train"] & sets["test"] or sets["val"] & sets["test"])
    summary_splits[kind] = {k: len(v) for k, v in parts.items()}
    for split, paths in parts.items():
        print(f"{kind:12s} {split:5s}: {len(paths)} imágenes")
        rows += [f"{kind},{split},{p.relative_to(DATA)}" for p in paths]
print("✅ Sin fuga: ningún grupo aparece en dos conjuntos")
(WORK / "splits.csv").write_text("tipo,split,archivo\\n" + "\\n".join(rows), encoding="utf-8")
summary["splits"] = summary_splits
(WORK / "resumen_etapa1.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
"""),
    md("## 6. Ejemplos con recuadros (capturas para la bitácora)"),
    code("""
def to_display(im: Image.Image) -> Image.Image:
    \"\"\"Las radiografías de 16 bits se ven negras o blancas si no se normalizan.\"\"\"
    if im.mode in ("I;16", "I;16B", "I", "F"):
        a = np.asarray(im, dtype=np.float32)
        lo, hi = np.percentile(a, [1, 99])
        a = np.clip((a - lo) / max(hi - lo, 1e-6), 0, 1)
        return Image.fromarray((a * 255).astype("uint8"))
    return im


def pick_varied(items: dict, kind: str, per_class: int = 2, n: int = 6) -> list:
    chosen, seen, used_groups = [], Counter(), set()
    for p, b in sorted(items.items()):
        main = Counter(x.label for x in b).most_common(1)
        if main and seen[main[0][0]] < per_class and groups[kind][p] not in used_groups:
            chosen.append((p, b))
            seen[main[0][0]] += 1
            used_groups.add(groups[kind][p])
        if len(chosen) == n:
            break
    return chosen


def grid(items, title, out_name):
    if not items:
        print("Sin ejemplos para", title)
        return
    cols = 3
    rows_n = (len(items) + cols - 1) // cols
    fig, axes = plt.subplots(rows_n, cols, figsize=(15, 5 * rows_n), squeeze=False)
    for ax in axes.flat:
        ax.axis("off")
    for ax, (path, boxes) in zip(axes.flat, items):
        with Image.open(path) as im:
            ax.imshow(draw_boxes(to_display(im), boxes))
        ax.set_title(", ".join(f"{k}: {v}" for k, v in summarize(boxes).items()), fontsize=10)
    fig.suptitle(title, fontsize=14)
    plt.tight_layout()
    plt.savefig(WORK / out_name, dpi=130)
    plt.show()


grid(pick_varied(datasets.get("radiografias", {}), "radiografias"),
     "Radiografías: defectos marcados (rojo)", "ejemplos_radiografias.png")
grid(pick_varied(datasets.get("cordones", {}), "cordones"),
     "Fotos de cordones: rojo = defecto, ámbar = cordón malo, verde = cordón bueno", "ejemplos_cordones.png")
print("Listo. Descargá el notebook con File → Download Notebook y pasáselo a Claude.")
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
