"""Inferencia con el modelo exportado a ONNX (RT-DETR).

El modelo recibe una imagen RGB de 640x640 con valores entre 0 y 1 y devuelve, para cada
una de sus 300 "consultas", un puntaje por clase (`logits`) y un recuadro relativo en
formato centro-ancho-alto (`pred_boxes`). Acá se convierte eso en recuadros `Box`
en píxeles de la imagen original.

La sesión de ONNX se recibe desde afuera para poder testear sin el modelo real.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import numpy as np
from PIL import Image

from revision_pipes.annotations import Box
from revision_pipes.tiling import merge, to_plate, windows

INPUT_SIZE = 640


class Session(Protocol):
    def run(self, output_names, input_feed: dict) -> list: ...


def prepare(image: Image.Image, size: int = INPUT_SIZE) -> np.ndarray:
    """Imagen → tensor (1, 3, size, size) float32 en [0, 1], como en el entrenamiento."""
    rgb = image.convert("RGB").resize((size, size), Image.Resampling.BILINEAR)
    array = np.asarray(rgb, dtype=np.float32) / 255.0
    return array.transpose(2, 0, 1)[None]


def decode(
    logits: np.ndarray,
    pred_boxes: np.ndarray,
    image_size: tuple[int, int],
    labels: Sequence[str],
    threshold: float,
) -> list[Box]:
    """Convierte la salida cruda del modelo en recuadros por encima del umbral."""
    if logits.ndim == 3:
        logits, pred_boxes = logits[0], pred_boxes[0]
    if logits.shape[-1] != len(labels):
        raise ValueError(f"El modelo tiene {logits.shape[-1]} clases y se pasaron {len(labels)}.")
    scores = 1.0 / (1.0 + np.exp(-logits))  # RT-DETR usa sigmoide por clase
    best_class = scores.argmax(axis=1)
    best_score = scores.max(axis=1)
    width, height = image_size
    boxes = []
    for query in np.argsort(-best_score, kind="stable"):
        score = float(best_score[query])
        if score < threshold:
            break
        cx, cy, w, h = pred_boxes[query]
        boxes.append(
            Box(
                x_min=float((cx - w / 2) * width),
                y_min=float((cy - h / 2) * height),
                x_max=float((cx + w / 2) * width),
                y_max=float((cy + h / 2) * height),
                label=labels[int(best_class[query])],
                score=score,
            ).clip(width, height)
        )
    return [b for b in boxes if b.is_valid()]


class Detector:
    """Envuelve una sesión de ONNX Runtime con las etiquetas y el umbral elegidos."""

    def __init__(self, session: Session, labels: Sequence[str], threshold: float):
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("El umbral debe estar entre 0 y 1.")
        self.session = session
        self.labels = list(labels)
        self.threshold = threshold

    @classmethod
    def from_file(cls, model_path: str, labels: Sequence[str], threshold: float) -> Detector:
        import onnxruntime as ort  # opcional: solo hace falta para usar el modelo real

        session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        return cls(session, labels, threshold)

    def predict(self, image: Image.Image) -> list[Box]:
        """Detecta en la imagen. Si es alargada, la corta en ventanas superpuestas y une."""
        found = []
        for window in windows(*image.size):
            crop = image.crop(window)
            logits, pred_boxes = self.session.run(None, {"pixel_values": prepare(crop)})[:2]
            found += to_plate(decode(logits, pred_boxes, crop.size, self.labels, self.threshold),
                              window)
        return merge(found)
