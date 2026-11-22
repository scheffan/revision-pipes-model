"""Celdas del notebook de Kaggle de la Etapa 2 (entrenamiento del detector RT-DETR).

Las usa scripts/build_kaggle_notebook.py. El código de las celdas va como texto.
"""

INTRO = """
# Etapa 2 · Modelo — revisión remota de soldaduras

Entrena un detector **RT-DETR** (licencia Apache 2.0) para marcar defectos y evalúa honestamente:

1. Baja los mismos datasets que la Etapa 1 y los separa con la **misma semilla** (mismos conjuntos).
2. Ajusta un RT-DETR liviano (R18) preentrenado, con variaciones suaves solo en entrenamiento.
3. Elige el umbral de confianza en **validación** para que casi no se escapen placas con defectos.
4. Mide en **prueba** (imágenes que el modelo nunca vio): mAP@50, recall y precisión por clase,
   recall por placa, y arma la galería de "dónde falla".
5. Exporta el modelo a **ONNX** para la app.

**Antes de correr:** *Settings → Accelerator: GPU*, *Internet: On* y el secreto `ROBOFLOW_API_KEY`.
Para que corra aunque cierres el navegador: **Save Version → Save & Run All (Commit)**.
"""

CONFIG = """
import os

MODULO = "radiografias"      # "radiografias" o "cordones"
EPOCHS = 25                   # el primer modelo llegó a su mejor valor en la época 13
IMG_SIZE = 640
BATCH = 8
LR = 1e-4                     # cabeza del detector
LR_BACKBONE = 1e-5            # el backbone preentrenado se ajusta más suave
SEED = 42                     # la misma de la Etapa 1: mismos conjuntos
TARGET_RECALL = 0.97          # en validación se apunta más alto: margen para que en prueba quede ≥ 95 %
OVERLAP = 0.25                # superposición de las ventanas en placas alargadas
MIN_RATIO = 1.5               # desde qué proporción (largo / corto) se corta en ventanas
VERSION = "v2-ventanas"
TIME_LIMIT_H = 3.0            # corte de seguridad para no agotar la cuota de GPU
MODEL_ID = "PekingU/rtdetr_r18vd_coco_o365"
DRY_RUN = os.environ.get("DRY_RUN") == "1"  # prueba rápida con un modelo chico, sin GPU

SOURCES = {
    "rx_weld": ("kunkun-vhmx2", "weld-2z7bw", 1, "radiografias"),
    "rx_weld_data": ("vayun-goel-jlreu", "weld-data-4ln0h", None, "radiografias"),
    "cordones_ccby": ("computer-vision-5vq1v", "welding_defects-2tvbr", 1, "cordones"),
    "cordones_dominio_publico": ("computer-vision-pl2fz", "welding-defects-detection-ru1eb", None, "cordones"),
}
SOURCES = {k: v for k, v in SOURCES.items() if v[3] == MODULO}
"""

IMPORTS = """
import json, math, random, time
from collections import Counter
from pathlib import Path

import imagehash
import matplotlib.pyplot as plt
import numpy as np
import torch
from PIL import Image, ImageEnhance

from revision_pipes.annotations import Box, clean, from_coco, iou
from revision_pipes.inference import decode
from revision_pipes.metrics import choose_threshold, image_recall, per_class
from revision_pipes.splits import split_by_group
from revision_pipes.tiling import boxes_in_window, merge, to_plate, windows
from revision_pipes.taxonomy import (
    TRAINING_CLASSES_CORDONES, TRAINING_CLASSES_RX, normalize_label, to_training_class,
)
from revision_pipes.visualize import draw_boxes, summarize

random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print("Dispositivo:", DEVICE, torch.cuda.get_device_name(0) if DEVICE == "cuda" else "")
WORK = Path("/kaggle/working")
DATA = Path("/tmp/data")
DATA.mkdir(parents=True, exist_ok=True)
LABELS = TRAINING_CLASSES_RX if MODULO == "radiografias" else TRAINING_CLASSES_CORDONES
# Clases que cuentan como "hay un problema" para el recall por imagen y las falsas alarmas.
# En cordones, "Good Weld" es un recuadro verde: no es un defecto.
DEFECT_LABELS = set(LABELS) - {"Good Weld"}


def defects(boxes):
    return [b for b in boxes if b.label in DEFECT_LABELS]
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
"""

LOAD_SPLIT = """
def load_coco_folder(folder: Path) -> dict:
    result = {}
    for ann_file in folder.rglob("_annotations.coco.json"):
        for file_name, boxes in from_coco(json.loads(ann_file.read_text())).items():
            image_path = ann_file.parent / file_name
            if not image_path.exists():
                continue
            if MODULO == "radiografias":
                mapped = []
                for b in boxes:
                    label = to_training_class(normalize_label(b.label))
                    if label:
                        mapped.append(Box(b.x_min, b.y_min, b.x_max, b.y_max, label))
                boxes = mapped
            boxes = [b for b in boxes if b.label in LABELS]
            with Image.open(image_path) as im:
                result[image_path] = clean(boxes, *im.size)
    return result


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


items = {}
for name in SOURCES:
    items.update(load_coco_folder(DATA / name))
groups = group_images(sorted(items))
splits = split_by_group(sorted(items), lambda p: groups[p], seed=SEED)
# En validación y prueba se deja UNA imagen por grupo: las copias aumentadas (rotadas,
# espejadas) de la misma foto contarían el mismo caso varias veces.
for split in ("val", "test"):
    seen, unique = set(), []
    for p in splits[split]:
        if groups[p] not in seen:
            seen.add(groups[p])
            unique.append(p)
    splits[split] = unique
for split, paths in splits.items():
    counts = Counter(b.label for p in paths for b in items[p])
    print(f"{split:5s}: {len(paths)} imágenes · {dict(counts.most_common())}")

# Placas alargadas → ventanas cuadradas superpuestas. Todas las ventanas de una placa quedan
# en el mismo conjunto que la placa (sin fuga).
sizes = {}
for p in items:
    with Image.open(p) as im:
        sizes[p] = im.size
plate_windows = {p: windows(*sizes[p], overlap=OVERLAP, min_ratio=MIN_RATIO) for p in items}
samples = {
    split: [(p, w, boxes_in_window(items[p], w)) for p in paths for w in plate_windows[p]]
    for split, paths in splits.items()
}
for split, ss in samples.items():
    healthy = sum(1 for _, _, b in ss if not b)
    print(f"{split:5s}: {len(ss)} ventanas de entrenamiento · {healthy} sin defectos (zonas sanas)")
"""

DATASET = """
def augment(image: Image.Image, boxes: list) -> tuple:
    \"\"\"Variaciones suaves: espejado, rotación de 90°, brillo y contraste. Solo en entrenamiento.\"\"\"
    if random.random() < 0.5:
        w = image.width
        image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        boxes = [Box(w - b.x_max, b.y_min, w - b.x_min, b.y_max, b.label) for b in boxes]
    if random.random() < 0.3:
        # Rotación de 90° (antihoraria) para aprender soldaduras verticales: (x, y) → (y, W - x)
        w = image.width
        image = image.transpose(Image.Transpose.ROTATE_90)
        boxes = [Box(b.y_min, w - b.x_max, b.y_max, w - b.x_min, b.label) for b in boxes]
    image = ImageEnhance.Brightness(image).enhance(random.uniform(0.8, 1.2))
    image = ImageEnhance.Contrast(image).enhance(random.uniform(0.8, 1.2))
    return image, boxes


class DetectionDataset(torch.utils.data.Dataset):
    def __init__(self, samples: list, train: bool):
        self.samples, self.train = samples, train

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, i):
        path, window, boxes = self.samples[i]
        image = Image.open(path).convert("RGB").crop(window)
        if self.train:
            image, boxes = augment(image, boxes)
        w, h = image.size
        pixels = image.resize((IMG_SIZE, IMG_SIZE), Image.Resampling.BILINEAR)
        pixels = torch.from_numpy(np.asarray(pixels, dtype=np.float32) / 255.0).permute(2, 0, 1)
        # RT-DETR espera recuadros relativos en formato centro-ancho-alto
        rel = [[(b.x_min + b.x_max) / 2 / w, (b.y_min + b.y_max) / 2 / h,
                (b.x_max - b.x_min) / w, (b.y_max - b.y_min) / h] for b in boxes]
        target = {
            "class_labels": torch.tensor([LABELS.index(b.label) for b in boxes], dtype=torch.long),
            "boxes": torch.tensor(rel, dtype=torch.float32).reshape(-1, 4),
        }
        return pixels, target


def collate(batch):
    return torch.stack([b[0] for b in batch]), [b[1] for b in batch]


loaders = {
    split: torch.utils.data.DataLoader(
        DetectionDataset(ss, train=(split == "train")), batch_size=BATCH,
        shuffle=(split == "train"), num_workers=2, collate_fn=collate,
    )
    for split, ss in samples.items()
}
"""

MODEL = """
from transformers import RTDetrConfig, RTDetrForObjectDetection

id2label = dict(enumerate(LABELS))
label2id = {v: k for k, v in id2label.items()}
if DRY_RUN:
    config = RTDetrConfig(num_labels=len(LABELS), id2label=id2label, label2id=label2id,
                          num_queries=50, decoder_layers=1, encoder_layers=1, d_model=64,
                          encoder_hidden_dim=64, decoder_in_channels=[64, 64, 64],
                          decoder_ffn_dim=128, encoder_ffn_dim=128,
                          use_pretrained_backbone=False)
    model = RTDetrForObjectDetection(config)
else:
    model = RTDetrForObjectDetection.from_pretrained(
        MODEL_ID, id2label=id2label, label2id=label2id, ignore_mismatched_sizes=True,
    )
model.to(DEVICE)
backbone = [p for n, p in model.named_parameters() if "backbone" in n]
rest = [p for n, p in model.named_parameters() if "backbone" not in n]
optimizer = torch.optim.AdamW(
    [{"params": rest, "lr": LR}, {"params": backbone, "lr": LR_BACKBONE}], weight_decay=1e-4
)
steps = EPOCHS * max(1, len(loaders["train"]))
scheduler = torch.optim.lr_scheduler.LambdaLR(
    optimizer, lambda s: min(1.0, (s + 1) / 200) * 0.5 * (1 + math.cos(math.pi * min(s, steps) / steps))
)
print(f"Parámetros: {sum(p.numel() for p in model.parameters()) / 1e6:.1f} M")
"""

PREDICT = """
@torch.no_grad()
def predict(split: str, threshold: float = 0.01, per_window: bool = False):
    \"\"\"Recuadros predichos por placa (en píxeles de la placa), detectando ventana por ventana
    y uniendo duplicados. Con per_window=True devuelve además lo hallado en cada ventana.\"\"\"
    model.eval()
    jobs = [(p, w) for p in splits[split] for w in plate_windows[p]]
    found_by_job = []
    for start in range(0, len(jobs), BATCH):
        batch = jobs[start:start + BATCH]
        crops = []
        for p, w in batch:
            with Image.open(p) as im:
                crops.append(im.convert("RGB").crop(w))
        pixels = torch.stack([
            torch.from_numpy(np.asarray(c.resize((IMG_SIZE, IMG_SIZE)), dtype=np.float32) / 255.0)
            .permute(2, 0, 1) for c in crops
        ]).to(DEVICE)
        out = model(pixel_values=pixels)
        for k, c in enumerate(crops):
            found_by_job.append(decode(out.logits[k].float().cpu().numpy(), out.pred_boxes[k].float().cpu().numpy(),
                                       c.size, LABELS, threshold))
    by_plate = {p: [] for p in splits[split]}
    for (p, w), found in zip(jobs, found_by_job):
        by_plate[p] += to_plate(found, w)
    plates = [merge(by_plate[p]) for p in splits[split]]
    if per_window:
        return plates, list(zip(jobs, found_by_job))
    return plates


def map50(split: str, preds: list) -> dict:
    from torchmetrics.detection import MeanAveragePrecision

    metric = MeanAveragePrecision(iou_type="bbox", class_metrics=True)

    def tensors(boxes, with_scores):
        d = {
            "boxes": torch.tensor([[b.x_min, b.y_min, b.x_max, b.y_max] for b in boxes], dtype=torch.float32).reshape(-1, 4),
            "labels": torch.tensor([LABELS.index(b.label) for b in boxes], dtype=torch.long),
        }
        if with_scores:
            d["scores"] = torch.tensor([b.score for b in boxes], dtype=torch.float32)
        return d

    metric.update([tensors(p, True) for p in preds], [tensors(items[path], False) for path in splits[split]])
    r = metric.compute()
    per = {}
    if r["map_per_class"].numel() > 1:
        for cls_id, value in zip(r["classes"].tolist(), r["map_per_class"].tolist()):
            per[LABELS[cls_id]] = round(value, 4)
    return {"map50": round(float(r["map_50"]), 4), "map50_95": round(float(r["map"]), 4), "map50_95_por_clase": per}
"""

TRAIN = """
history, best_map, best_epoch, started = [], -1.0, -1, time.time()
best_dir = WORK / f"modelo_{MODULO}"
scaler = torch.amp.GradScaler("cuda", enabled=(DEVICE == "cuda"))

for epoch in range(1, EPOCHS + 1):
    model.train()
    losses = []
    for pixels, targets in loaders["train"]:
        pixels = pixels.to(DEVICE)
        targets = [{k: v.to(DEVICE) for k, v in t.items()} for t in targets]
        with torch.autocast(device_type="cuda", enabled=(DEVICE == "cuda")):
            loss = model(pixel_values=pixels, labels=targets).loss
        optimizer.zero_grad()
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 0.1)
        scaler.step(optimizer)
        scaler.update()
        scheduler.step()
        losses.append(loss.item())
    val = map50("val", predict("val"))
    history.append({"epoch": epoch, "loss": float(np.mean(losses)), "val_map50": val["map50"]})
    elapsed = (time.time() - started) / 3600
    print(f"Época {epoch:2d} · pérdida {history[-1]['loss']:.3f} · mAP@50 val {val['map50']:.3f} · {elapsed:.2f} h")
    if val["map50"] > best_map:
        best_map, best_epoch = val["map50"], epoch
        model.save_pretrained(best_dir)
    if elapsed > TIME_LIMIT_H:
        print("⏱️ Corte por tiempo: se usa la mejor época hasta acá.")
        break

model = RTDetrForObjectDetection.from_pretrained(best_dir).to(DEVICE)
print(f"Mejor época: {best_epoch} (mAP@50 en validación {best_map:.3f})")
"""

EVALUATE = """
# 1) Umbral elegido en VALIDACIÓN (nunca en prueba)
val_preds = predict("val")
val_truths = [items[p] for p in splits["val"]]
threshold = choose_threshold([defects(p) for p in val_preds], [defects(t) for t in val_truths], target_recall=TARGET_RECALL)
print(f"Umbral elegido en validación: {threshold} (recall por placa ≥ {TARGET_RECALL:.0%})")

# 2) Evaluación final en PRUEBA
test_preds, test_windows = predict("test", per_window=True)
test_truths = [items[p] for p in splits["test"]]

# Zonas sanas: ventanas de prueba sin ningún defecto marcado por el experto
healthy = [(job, found) for job, found in test_windows if not boxes_in_window(items[job[0]], job[1], min_visible=0.0)]
healthy_with_alarm = sum(1 for _, found in healthy if any(b.score >= threshold for b in found))
print(f"Zonas sanas en prueba: {len(healthy)} · con falsa alarma: {healthy_with_alarm}")

# Imágenes sin ningún defecto real (en cordones: solo cordón bueno): ¿el modelo inventa uno?
clean_imgs = [i for i, t in enumerate(test_truths) if not defects(t)]
clean_with_alarm = sum(1 for i in clean_imgs if any(b.score >= threshold for b in defects(test_preds[i])))
print(f"Imágenes sin defectos en prueba: {len(clean_imgs)} · con falsa alarma: {clean_with_alarm}")
coco = map50("test", test_preds)
classes = per_class(test_preds, test_truths, threshold)
metrics = {
    "modulo": MODULO,
    "version": VERSION,
    "modelo": MODEL_ID,
    "objetivo_recall_validacion": TARGET_RECALL,
    "mejor_epoca": best_epoch,
    "umbral": threshold,
    "imagenes_prueba": len(test_truths),
    "recall_por_placa": round(image_recall([defects(p) for p in test_preds], [defects(t) for t in test_truths], threshold), 4),
    "imagenes_sin_defecto_prueba": len(clean_imgs),
    "imagenes_sin_defecto_con_falsa_alarma": clean_with_alarm,
    "zonas_sanas_prueba": len(healthy),
    "zonas_sanas_con_falsa_alarma": healthy_with_alarm,
    **coco,
    "por_clase": {k: {"recall": round(m.recall, 4), "precision": round(m.precision, 4),
                      "aciertos": m.true_positives, "falsas_alarmas": m.false_positives,
                      "perdidos": m.false_negatives} for k, m in classes.items()},
    "historial": history,
}
(WORK / f"metricas_{MODULO}.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
print(json.dumps({k: v for k, v in metrics.items() if k != "historial"}, indent=2, ensure_ascii=False))
"""

FIGURES = """
def to_display(im):
    return im.convert("RGB")


fig, ax1 = plt.subplots(figsize=(8, 4))
ax1.plot([h["epoch"] for h in history], [h["loss"] for h in history], color="#2563eb", label="Pérdida (entrenamiento)")
ax1.set_xlabel("Época"); ax1.set_ylabel("Pérdida")
ax2 = ax1.twinx()
ax2.plot([h["epoch"] for h in history], [h["val_map50"] for h in history], color="#16a34a", label="mAP@50 (validación)")
ax2.set_ylabel("mAP@50")
fig.legend(loc="upper center", ncol=2)
plt.title(f"Entrenamiento · {MODULO}")
plt.tight_layout(); plt.savefig(WORK / f"curvas_{MODULO}.png", dpi=150); plt.show()


def comparison(indices, title, out_name):
    if not indices:
        print("Sin ejemplos para", title)
        return
    fig, axes = plt.subplots(len(indices), 2, figsize=(10, 5 * len(indices)), squeeze=False)
    for row, i in enumerate(indices):
        path = splits["test"][i]
        with Image.open(path) as im:
            im = to_display(im)
            axes[row][0].imshow(draw_boxes(im, test_truths[i]))
            axes[row][1].imshow(draw_boxes(im, [b for b in test_preds[i] if b.score >= threshold]))
        axes[row][0].set_title("Experto: " + (", ".join(f"{k}: {v}" for k, v in summarize(test_truths[i]).items()) or "sin defectos"), fontsize=9)
        found = [b for b in test_preds[i] if b.score >= threshold]
        axes[row][1].set_title("Modelo: " + (", ".join(f"{k}: {v}" for k, v in summarize(found).items()) or "sin hallazgos"), fontsize=9)
        for a in axes[row]:
            a.axis("off")
    fig.suptitle(title, fontsize=13)
    plt.tight_layout(); plt.savefig(WORK / out_name, dpi=110); plt.show()


def found(i):
    return [b for b in test_preds[i] if b.score >= threshold]


rng = random.Random(SEED)
with_defects = [i for i, t in enumerate(test_truths) if defects(t)]
good = [i for i in with_defects if defects(found(i))]
missed = [i for i in with_defects if not defects(found(i))]
false_alarm = [i for i, t in enumerate(test_truths) if not defects(t) and defects(found(i))]
comparison(rng.sample(good, min(4, len(good))), "Experto vs. modelo (conjunto de prueba)", f"predicciones_{MODULO}.png")
comparison((missed[:3] + false_alarm[:2]), "Dónde falla: placas con defecto sin marcar y falsas alarmas", f"donde_falla_{MODULO}.png")
print(f"Placas con defecto: {len(with_defects)} · marcadas: {len(good)} · sin marcar: {len(missed)} · falsas alarmas en placas sanas: {len(false_alarm)}")
"""

EXPORT = """
class Wrapper(torch.nn.Module):
    def __init__(self, m):
        super().__init__()
        self.m = m

    def forward(self, pixel_values):
        out = self.m(pixel_values=pixel_values)
        return out.logits, out.pred_boxes


onnx_path = WORK / f"modelo_{MODULO}.onnx"
try:
    model.eval().to("cpu")
    # Se exporta con una imagen real de validación (no con ruido: con ruido varias posiciones
    # empatan en puntaje y cada motor elige distinto).
    def as_tensor(path):
        with Image.open(path) as im:
            arr = np.asarray(im.convert("RGB").resize((IMG_SIZE, IMG_SIZE)), dtype=np.float32) / 255.0
        return torch.from_numpy(arr).permute(2, 0, 1)[None]

    sample = as_tensor(splits["val"][0])
    try:
        torch.onnx.export(Wrapper(model), (sample,), str(onnx_path), input_names=["pixel_values"],
                          output_names=["logits", "pred_boxes"], opset_version=17, dynamo=False)
    except Exception:
        torch.onnx.export(Wrapper(model), (sample,), str(onnx_path), input_names=["pixel_values"],
                          output_names=["logits", "pred_boxes"], opset_version=18, dynamo=True)
    import onnxruntime as ort

    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    size = (IMG_SIZE, IMG_SIZE)

    def findings_match(x):
        # Mismos hallazgos como conjunto (misma clase, IoU >= 0,9). Se ignoran los pegados
        # al umbral (+-0,02): un redondeo mínimo entre motores puede dejarlos de un lado
        # o del otro sin que nada esté mal.
        onnx_logits, onnx_boxes = session.run(None, {"pixel_values": x.numpy()})
        with torch.no_grad():
            ref = model(pixel_values=x)
        a = decode(onnx_logits[0], onnx_boxes[0], size, LABELS, threshold)
        b = decode(ref.logits[0].numpy(), ref.pred_boxes[0].numpy(), size, LABELS, threshold)
        firm = lambda boxes: [f for f in boxes if f.score >= threshold + 0.02]
        paired = lambda xs, ys: all(any(y.label == f.label and iou(f, y) >= 0.9 for y in ys) for f in xs)
        return paired(firm(a), b) and paired(firm(b), a)

    checked = splits["val"][:10]
    same = all(findings_match(as_tensor(p)) for p in checked)
    print(f"ONNX exportado ({onnx_path.stat().st_size / 1e6:.0f} MB) · mismos hallazgos que PyTorch en {len(checked)} imágenes: {'sí ✅' if same else 'NO ⚠️'}")
    (WORK / f"modelo_{MODULO}.json").write_text(json.dumps(
        {"labels": LABELS, "umbral": threshold, "img_size": IMG_SIZE, "modelo": MODEL_ID, "version": VERSION,
         "ventanas": {"overlap": OVERLAP, "min_ratio": MIN_RATIO},
         "onnx_verificado": same}, indent=2, ensure_ascii=False))
except Exception as error:
    print("⚠️ No se pudo exportar a ONNX (el modelo entrenado igual quedó guardado):", error)
print("Listo. Resultados en la pestaña Output.")
"""


def cells_etapa2(md, code, module_cell, modules, modulo="radiografias"):
    return [
        md(INTRO),
        md("## 1. Instalación y configuración"),
        code("!pip install -q roboflow imagehash torchmetrics pycocotools onnx onnxruntime\n"
             "import os\nos.makedirs('revision_pipes', exist_ok=True)\n"
             "open('revision_pipes/__init__.py', 'w').close()"),
        *[module_cell(name) for name in modules],
        code(CONFIG.replace('MODULO = "radiografias"', f'MODULO = "{modulo}"')),
        code(IMPORTS),
        md("## 2. Datos (mismos conjuntos que la Etapa 1)"),
        code(DOWNLOAD),
        code(LOAD_SPLIT),
        code(DATASET),
        md("## 3. Modelo y entrenamiento"),
        code(MODEL),
        code(PREDICT),
        code(TRAIN),
        md("## 4. Umbral (validación) y evaluación final (prueba)"),
        code(EVALUATE),
        md("## 5. Curvas, experto vs. modelo y dónde falla"),
        code(FIGURES),
        md("## 6. Exportación a ONNX para la app"),
        code(EXPORT),
    ]
