"""Celdas del notebook de Kaggle del "portero": clasifica la imagen antes de analizarla.

Responde si la imagen es una radiografía de soldadura, una foto de cordón u otra cosa, para que
la app no analice una foto con el modelo de radiografías (ni un gato con ninguno de los dos).
Las usa scripts/build_kaggle_notebook.py. El código de las celdas va como texto.
"""

INTRO = """
# Portero · ¿qué imagen es?

Antes de buscar defectos, la app tiene que saber **qué le subieron**. Cada detector busca defectos
en cualquier cosa que le den, así que una foto analizada como radiografía da resultados sin sentido.

Este notebook entrena un clasificador chico (**MobileNetV3-Small**, licencia BSD) con tres clases:

- **radiografia**: radiografías de soldadura (los mismos datasets de la Etapa 1).
- **foto_cordon**: fotos de cordones (los mismos datasets de la Etapa 1).
- **otra**: fotos comunes (Imagenette, Apache 2.0) y **radiografías de tórax** (CC BY 4.0), que son
  la trampa más difícil: son radiografías, pero no de soldadura.

Mide en prueba la exactitud por clase y la matriz de confusión, y exporta a ONNX.

**Antes de correr:** *Accelerator: GPU*, *Internet: On*, el secreto `ROBOFLOW_API_KEY` y, en
*Add Input*, el dataset **paultimothymooney/chest-xray-pneumonia**.
"""

CONFIG = """
import os

EPOCHS = 8
IMG_SIZE = 224
BATCH = 64
LR = 3e-4
SEED = 42
MAX_OTRAS_FOTOS = 3000        # de Imagenette
MAX_TORAX = 1500              # radiografías de tórax
UNSURE_BELOW = 0.6            # por debajo de esta confianza la app dice "no estoy seguro"
DRY_RUN = os.environ.get("DRY_RUN") == "1"

SOURCES = {
    "rx_weld": ("kunkun-vhmx2", "weld-2z7bw", 1, "radiografia"),
    "rx_weld_data": ("vayun-goel-jlreu", "weld-data-4ln0h", None, "radiografia"),
    "cordones_ccby": ("computer-vision-5vq1v", "welding_defects-2tvbr", 1, "foto_cordon"),
    "cordones_dominio_publico": ("computer-vision-pl2fz", "welding-defects-detection-ru1eb", None, "foto_cordon"),
}
LABELS = ["radiografia", "foto_cordon", "otra"]
"""

IMPORTS = """
import json, random, time
from collections import Counter
from pathlib import Path

import imagehash
import matplotlib.pyplot as plt
import numpy as np
import torch
import torchvision
from PIL import Image
from torchvision import transforms as T

from revision_pipes.splits import split_by_group

random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print("Dispositivo:", DEVICE, torch.cuda.get_device_name(0) if DEVICE == "cuda" else "")
WORK = Path("/kaggle/working")
DATA = Path("/tmp/data")
DATA.mkdir(parents=True, exist_ok=True)
"""

DOWNLOAD = """
if not DRY_RUN:
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
        print(f"{name} → versión {version}")
        project.version(version).download("coco", location=str(DATA / name))

    # Fotos comunes para la clase "otra" (Imagenette 160 px, Apache 2.0)
    for split in ("train", "val"):
        try:
            torchvision.datasets.Imagenette(str(DATA / "imagenette"), split=split, size="160px", download=True)
        except RuntimeError:
            pass  # ya estaba descargado
"""

COLLECT = """
EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def images_in(folder: Path) -> list:
    # Los zips armados en Mac traen copias basura ("__MACOSX/._foto.jpg") que no son imágenes
    return sorted(
        p for p in folder.rglob("*")
        if p.suffix.lower() in EXTS and not p.name.startswith("._") and "__MACOSX" not in p.parts
    )


def original_name(path: Path) -> str:
    return path.name.split(".rf.")[0]


def group_images(paths: list) -> dict:
    \"\"\"Mismo agrupamiento que la Etapa 1: copias aumentadas y fotos casi idénticas juntas.\"\"\"
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


# Soldadura: mismos datasets y misma separación sin fuga que la Etapa 1
label_of, group_of, source_of = {}, {}, {}
for name, (_, _, _, kind) in SOURCES.items():
    for p in images_in(DATA / name):
        label_of[p], source_of[p] = kind, name
weld = sorted(label_of)
group_of.update(group_images(weld))

# "Otra": fotos comunes y radiografías de tórax. Cada imagen es su propio grupo.
rng = random.Random(SEED)
fotos = images_in(DATA / "imagenette")
rng.shuffle(fotos)
torax = [p for p in images_in(Path("/kaggle/input")) if "chest" in str(p).lower()]
rng.shuffle(torax)
if not torax:
    print("⚠️ No encontré las radiografías de tórax: agregá el dataset chest-xray-pneumonia en Add Input.")
for p in fotos[:MAX_OTRAS_FOTOS]:
    label_of[p], group_of[p], source_of[p] = "otra", str(p), "imagenette"
for p in torax[:MAX_TORAX]:
    label_of[p], group_of[p], source_of[p] = "otra", str(p), "torax"

paths = sorted(label_of)
splits = split_by_group(paths, lambda p: group_of[p], seed=SEED)
# En validación y prueba, una sola imagen por grupo (sin copias rotadas o espejadas)
for split in ("val", "test"):
    seen, unique = set(), []
    for p in splits[split]:
        if group_of[p] not in seen:
            seen.add(group_of[p])
            unique.append(p)
    splits[split] = unique
for split, ps in splits.items():
    print(f"{split:5s}: {len(ps)} imágenes · {dict(Counter(label_of[p] for p in ps))}"
          f" · tórax: {sum(source_of[p] == 'torax' for p in ps)}")
"""

DATASET = """
MEAN, STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]

train_tf = T.Compose([
    T.RandomResizedCrop(IMG_SIZE, scale=(0.4, 1.0), ratio=(0.25, 4.0)),
    T.RandomHorizontalFlip(), T.RandomVerticalFlip(),
    T.RandomApply([T.RandomRotation((90, 90))], p=0.3),
    T.ColorJitter(0.3, 0.3, 0.2),
    T.RandomGrayscale(0.15),   # una foto en blanco y negro sigue siendo una foto
    T.ToTensor(),
])
# Igual que en la app: la imagen entera, estirada a un cuadrado, con valores entre 0 y 1.
# La normalización de ImageNet va dentro del modelo exportado.
eval_tf = T.Compose([T.Resize((IMG_SIZE, IMG_SIZE)), T.ToTensor()])


class Images(torch.utils.data.Dataset):
    def __init__(self, ps, tf):
        self.ps, self.tf = ps, tf

    def __len__(self):
        return len(self.ps)

    def __getitem__(self, i):
        with Image.open(self.ps[i]) as im:
            x = self.tf(im.convert("RGB"))
        return x, LABELS.index(label_of[self.ps[i]])


# Clases desbalanceadas: cada clase sale con la misma frecuencia en entrenamiento
counts = Counter(label_of[p] for p in splits["train"])
weights = [1.0 / counts[label_of[p]] for p in splits["train"]]
sampler = torch.utils.data.WeightedRandomSampler(weights, num_samples=len(weights), replacement=True)
loaders = {
    "train": torch.utils.data.DataLoader(Images(splits["train"], train_tf), batch_size=BATCH, sampler=sampler, num_workers=2),
    "val": torch.utils.data.DataLoader(Images(splits["val"], eval_tf), batch_size=BATCH, num_workers=2),
    "test": torch.utils.data.DataLoader(Images(splits["test"], eval_tf), batch_size=BATCH, num_workers=2),
}
"""

MODEL = """
class Portero(torch.nn.Module):
    \"\"\"MobileNetV3-Small con la normalización adentro: recibe píxeles en [0, 1].\"\"\"

    def __init__(self):
        super().__init__()
        weights = None if DRY_RUN else torchvision.models.MobileNet_V3_Small_Weights.IMAGENET1K_V1
        self.net = torchvision.models.mobilenet_v3_small(weights=weights)
        self.net.classifier[3] = torch.nn.Linear(self.net.classifier[3].in_features, len(LABELS))
        self.register_buffer("mean", torch.tensor(MEAN).view(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor(STD).view(1, 3, 1, 1))

    def forward(self, pixel_values):
        return self.net((pixel_values - self.mean) / self.std)


model = Portero().to(DEVICE)
optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-4)
scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=LR, total_steps=EPOCHS * len(loaders["train"]))
scaler = torch.amp.GradScaler(enabled=DEVICE == "cuda")


@torch.no_grad()
def probabilities(split):
    model.eval()
    out = []
    for x, _ in loaders[split]:
        with torch.autocast(DEVICE, enabled=DEVICE == "cuda"):
            out.append(torch.softmax(model(x.to(DEVICE)).float(), 1).cpu())
    return torch.cat(out).numpy()


def accuracy(split, probs):
    truth = np.array([LABELS.index(label_of[p]) for p in splits[split]])
    return float((probs.argmax(1) == truth).mean()), truth
"""

TRAIN = """
history, best = [], (-1.0, None)
start = time.time()
for epoch in range(1, EPOCHS + 1):
    model.train()
    total = 0.0
    for x, y in loaders["train"]:
        x, y = x.to(DEVICE), y.to(DEVICE)
        with torch.autocast(DEVICE, enabled=DEVICE == "cuda"):
            loss = torch.nn.functional.cross_entropy(model(x), y, label_smoothing=0.05)
        optimizer.zero_grad()
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()
        scheduler.step()
        total += loss.item()
    acc, _ = accuracy("val", probabilities("val"))
    history.append({"epoca": epoch, "perdida": total / len(loaders["train"]), "exactitud_val": acc})
    print(f"Época {epoch:2d} · pérdida {history[-1]['perdida']:.4f} · exactitud val {acc:.4f} · {(time.time() - start) / 60:.1f} min")
    if acc > best[0]:
        best = (acc, {k: v.detach().clone() for k, v in model.state_dict().items()})
model.load_state_dict(best[1])
print(f"Mejor exactitud en validación: {best[0]:.4f}")
"""

EVALUATE = """
probs = probabilities("test")
acc, truth = accuracy("test", probs)
pred = probs.argmax(1)
conf = probs.max(1)
confusion = np.zeros((len(LABELS), len(LABELS)), dtype=int)
for t, p in zip(truth, pred):
    confusion[t, p] += 1

por_clase = {}
for i, label in enumerate(LABELS):
    mask = truth == i
    por_clase[label] = {"imagenes": int(mask.sum()), "exactitud": round(float((pred[mask] == i).mean()), 4)}
test_sources = np.array([source_of[p] for p in splits["test"]])
torax_mask = test_sources == "torax"
unsure = conf < UNSURE_BELOW
metrics = {
    "modelo": "mobilenet_v3_small (torchvision, ImageNet)",
    "labels": LABELS,
    "imagenes_prueba": int(len(truth)),
    "exactitud": round(acc, 4),
    "por_clase": por_clase,
    "matriz_confusion": {"filas_verdad_columnas_prediccion": LABELS, "valores": confusion.tolist()},
    "torax_prueba": int(torax_mask.sum()),
    "torax_tomadas_por_radiografia_de_soldadura": int(((pred == 0) & torax_mask).sum()),
    "umbral_no_seguro": UNSURE_BELOW,
    "no_seguro_prueba": int(unsure.sum()),
    "errores_con_confianza_alta": int(((pred != truth) & ~unsure).sum()),
    "mejor_exactitud_validacion": round(best[0], 4),
}
print(json.dumps(metrics, indent=2, ensure_ascii=False))
(WORK / "metricas_portero.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
"""

FIGURES = """
fig, ax = plt.subplots(figsize=(5, 4))
ax.imshow(confusion, cmap="Blues")
ax.set_xticks(range(len(LABELS)), LABELS, rotation=20)
ax.set_yticks(range(len(LABELS)), LABELS)
ax.set_xlabel("Lo que dijo el portero")
ax.set_ylabel("Lo que era")
for i in range(len(LABELS)):
    for j in range(len(LABELS)):
        ax.text(j, i, confusion[i, j], ha="center", va="center", color="black")
ax.set_title("Portero · matriz de confusión (prueba)")
fig.tight_layout()
fig.savefig(WORK / "confusion_portero.png", dpi=120)
plt.show()

errors = [i for i in range(len(truth)) if pred[i] != truth[i]][:12]
if errors:
    cols = 4
    rows = (len(errors) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(3 * cols, 3 * rows))
    for ax in np.atleast_1d(axes).ravel():
        ax.axis("off")
    for ax, i in zip(np.atleast_1d(axes).ravel(), errors):
        with Image.open(splits["test"][i]) as im:
            ax.imshow(im.convert("RGB"))
        ax.set_title(f"era {LABELS[truth[i]]}\\ndijo {LABELS[pred[i]]} {conf[i]:.0%}", fontsize=8)
    fig.suptitle("Portero · errores en prueba")
    fig.tight_layout()
    fig.savefig(WORK / "errores_portero.png", dpi=110)
    plt.show()
else:
    print("Sin errores en prueba.")
"""

EXPORT = """
onnx_path = WORK / "modelo_portero.onnx"
model.eval().to("cpu")
sample = torch.stack([eval_tf(Image.open(p).convert("RGB")) for p in splits["val"][:8]])


class WithSoftmax(torch.nn.Module):
    def __init__(self, m):
        super().__init__()
        self.m = m

    def forward(self, pixel_values):
        return torch.softmax(self.m(pixel_values), dim=1)


# El envoltorio se pone en modo evaluación: si no, al terminar la exportación el modelo queda en
# modo entrenamiento y la comparación de abajo se haría contra otra cosa.
torch.onnx.export(WithSoftmax(model).eval(), (sample[:1],), str(onnx_path), input_names=["pixel_values"],
                  output_names=["probabilities"], opset_version=17, dynamo=False)
model.eval()
import onnxruntime as ort

session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
same = True
for x in sample:
    onnx_p = session.run(None, {"pixel_values": x[None].numpy()})[0][0]
    with torch.no_grad():
        ref = torch.softmax(model(x[None]), 1)[0].numpy()
    same &= bool(onnx_p.argmax() == ref.argmax() and np.abs(onnx_p - ref).max() < 1e-3)
print(f"ONNX exportado ({onnx_path.stat().st_size / 1e6:.1f} MB) · misma respuesta que PyTorch en {len(sample)} imágenes: {'sí ✅' if same else 'NO ⚠️'}")
(WORK / "modelo_portero.json").write_text(json.dumps({
    "labels": LABELS, "img_size": IMG_SIZE, "entrada": "RGB estirada a cuadrado, valores entre 0 y 1",
    "salida": "probabilidades por clase", "umbral_no_seguro": UNSURE_BELOW, "onnx_verificado": same,
}, indent=2, ensure_ascii=False))
print("Listo. Resultados en la pestaña Output.")
"""


def cells_portero(md, code, module_cell):
    return [
        md(INTRO),
        md("## 1. Instalación y configuración"),
        code(
            "!pip install -q roboflow imagehash onnx onnxruntime\n"
            "import os\nos.makedirs('revision_pipes', exist_ok=True)\n"
            "open('revision_pipes/__init__.py', 'w').close()"
        ),
        module_cell("splits.py"),
        code(CONFIG),
        code(IMPORTS),
        md("## 2. Datos"),
        code(DOWNLOAD),
        code(COLLECT),
        code(DATASET),
        md("## 3. Modelo y entrenamiento"),
        code(MODEL),
        code(TRAIN),
        md("## 4. Evaluación en prueba"),
        code(EVALUATE),
        code(FIGURES),
        md("## 5. Exportación a ONNX"),
        code(EXPORT),
    ]
