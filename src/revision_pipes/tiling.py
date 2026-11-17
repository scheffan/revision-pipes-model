"""Ventanas superpuestas para placas alargadas.

Una placa completa puede medir 3000 × 600 píxeles. Si se achica entera al cuadrado de
640 × 640 que recibe el modelo, un poro de pocos píxeles desaparece. En cambio se corta
en ventanas cuadradas (del lado más corto) que se pisan un 25 %, se detecta en cada una
y los recuadros se devuelven a coordenadas de la placa, uniendo los duplicados.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from revision_pipes.annotations import Box, iou

Window = tuple[int, int, int, int]  # x_min, y_min, x_max, y_max


def windows(width: int, height: int, overlap: float = 0.25, min_ratio: float = 1.5) -> list[Window]:
    """Ventanas cuadradas que cubren toda la imagen.

    Si la imagen es casi cuadrada (lado largo / lado corto < min_ratio), devuelve una sola
    ventana con la imagen entera.
    """
    if not 0.0 <= overlap < 1.0:
        raise ValueError("La superposición debe estar entre 0 y 1 (sin incluir 1).")
    long_side, short_side = max(width, height), min(width, height)
    if short_side <= 0:
        raise ValueError("La imagen no tiene tamaño.")
    if long_side / short_side < min_ratio:
        return [(0, 0, width, height)]
    step = max(1, int(short_side * (1 - overlap)))
    starts = list(range(0, long_side - short_side, step)) + [long_side - short_side]
    starts = sorted(set(starts))
    if width >= height:
        return [(s, 0, s + short_side, height) for s in starts]
    return [(0, s, width, s + short_side) for s in starts]


def boxes_in_window(boxes: Iterable[Box], window: Window, min_visible: float = 0.4) -> list[Box]:
    """Recuadros de la placa expresados dentro de la ventana.

    Un recuadro cortado por el borde se conserva solo si queda visible al menos
    `min_visible` de su área.
    """
    x0, y0, x1, y1 = window
    result = []
    for b in boxes:
        clipped = Box(
            max(b.x_min, x0), max(b.y_min, y0), min(b.x_max, x1), min(b.y_max, y1), b.label, b.score
        )
        if clipped.width <= 0 or clipped.height <= 0 or b.area <= 0:
            continue
        if clipped.area / b.area < min_visible:
            continue
        result.append(
            Box(clipped.x_min - x0, clipped.y_min - y0, clipped.x_max - x0, clipped.y_max - y0,
                b.label, b.score)
        )
    return result


def to_plate(boxes: Iterable[Box], window: Window) -> list[Box]:
    """Pasa recuadros de coordenadas de la ventana a coordenadas de la placa."""
    x0, y0 = window[0], window[1]
    return [Box(b.x_min + x0, b.y_min + y0, b.x_max + x0, b.y_max + y0, b.label, b.score)
            for b in boxes]


def merge(boxes: Sequence[Box], iou_threshold: float = 0.5) -> list[Box]:
    """Une duplicados de la misma clase (de ventanas que se pisan): queda el de más confianza."""
    ordered = sorted(boxes, key=lambda b: -(b.score if b.score is not None else 1.0))
    kept: list[Box] = []
    for b in ordered:
        if all(k.label != b.label or iou(k, b) < iou_threshold for k in kept):
            kept.append(b)
    return kept
