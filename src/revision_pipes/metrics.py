"""Métricas pensadas para el inspector.

- Recall por placa: de las placas que tienen al menos un defecto, ¿cuántas marcó el modelo?
  Es lo que más importa: una placa con defecto que pasa sin marcar es el peor error.
- Recall y precisión por clase, emparejando recuadros con IoU ≥ 0,5.
- Elección del umbral de confianza: el más alto que todavía cumple el recall pedido.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from revision_pipes.annotations import Box, iou


@dataclass(frozen=True)
class ClassMetrics:
    label: str
    true_positives: int
    false_positives: int
    false_negatives: int

    @property
    def recall(self) -> float:
        total = self.true_positives + self.false_negatives
        return self.true_positives / total if total else 0.0

    @property
    def precision(self) -> float:
        total = self.true_positives + self.false_positives
        return self.true_positives / total if total else 0.0


def above(boxes: Sequence[Box], threshold: float) -> list[Box]:
    return [b for b in boxes if (b.score if b.score is not None else 1.0) >= threshold]


def image_recall(
    predictions: Sequence[Sequence[Box]], truths: Sequence[Sequence[Box]], threshold: float
) -> float:
    """Proporción de imágenes con defectos reales donde el modelo marcó al menos uno."""
    with_defects = [i for i, t in enumerate(truths) if t]
    if not with_defects:
        return 0.0
    hits = sum(1 for i in with_defects if above(predictions[i], threshold))
    return hits / len(with_defects)


def choose_threshold(
    predictions: Sequence[Sequence[Box]],
    truths: Sequence[Sequence[Box]],
    target_recall: float = 0.95,
    candidates: Sequence[float] | None = None,
) -> float:
    """El umbral más alto (menos falsas alarmas) que cumple el recall por placa pedido.

    Si ninguno lo cumple, devuelve el más bajo de los candidatos.
    """
    if candidates is None:
        candidates = [round(0.05 * i, 2) for i in range(1, 20)]
    for threshold in sorted(candidates, reverse=True):
        if image_recall(predictions, truths, threshold) >= target_recall:
            return threshold
    return min(candidates)


def per_class(
    predictions: Sequence[Sequence[Box]],
    truths: Sequence[Sequence[Box]],
    threshold: float,
    iou_threshold: float = 0.5,
) -> dict[str, ClassMetrics]:
    """Empareja recuadros predichos y reales de la misma clase (cada real se usa una vez)."""
    counts: dict[str, list[int]] = {}
    for preds, gts in zip(predictions, truths, strict=True):
        preds = sorted(above(preds, threshold), key=lambda b: -(b.score or 1.0))
        used = [False] * len(gts)
        for p in preds:
            best, best_j = 0.0, -1
            for j, g in enumerate(gts):
                if not used[j] and g.label == p.label:
                    overlap = iou(p, g)
                    if overlap > best:
                        best, best_j = overlap, j
            c = counts.setdefault(p.label, [0, 0, 0])
            if best_j >= 0 and best >= iou_threshold:
                used[best_j] = True
                c[0] += 1
            else:
                c[1] += 1
        for j, g in enumerate(gts):
            if not used[j]:
                counts.setdefault(g.label, [0, 0, 0])[2] += 1
    return {k: ClassMetrics(k, *v) for k, v in sorted(counts.items())}
