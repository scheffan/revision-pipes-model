"""Dibujo de recuadros sobre la imagen: rojo para defectos, verde para zonas sanas.

Es el componente visual del proyecto: subo una placa o una foto y veo
dónde está el problema y dónde está bien.
"""

from __future__ import annotations

from collections.abc import Iterable

from PIL import Image, ImageDraw

from revision_pipes.annotations import Box

RED = (220, 38, 38)
GREEN = (22, 163, 74)
AMBER = (217, 119, 6)

# Etiquetas que se consideran "sanas" (se dibujan en verde). El resto va en rojo.
GOOD_LABELS = {"good weld", "good_weld", "ok", "sin defecto", "no defect", "pipe"}
# Etiquetas que indican un problema general (cordón malo), en ámbar.
WARNING_LABELS = {"bad weld", "bad_weld"}


def color_for(label: str) -> tuple[int, int, int]:
    key = label.strip().lower()
    if key in GOOD_LABELS:
        return GREEN
    if key in WARNING_LABELS:
        return AMBER
    return RED


def draw_boxes(
    image: Image.Image, boxes: Iterable[Box], show_numbers: bool = True
) -> Image.Image:
    """Devuelve una copia de la imagen con los recuadros numerados y coloreados."""
    canvas = image.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas)
    thickness = max(2, round(min(canvas.size) / 200))
    for number, box in enumerate(boxes, start=1):
        color = color_for(box.label)
        draw.rectangle(
            [box.x_min, box.y_min, box.x_max, box.y_max], outline=color, width=thickness
        )
        if show_numbers:
            tag = f"{number} {box.label}"
            left, top, right, bottom = draw.textbbox((box.x_min, box.y_min), tag)
            draw.rectangle([left - 2, top - 2, right + 2, bottom + 2], fill=color)
            draw.text((box.x_min, box.y_min), tag, fill=(255, 255, 255))
    return canvas


def summarize(boxes: Iterable[Box]) -> dict[str, int]:
    """Cuenta los recuadros por etiqueta (sirve también para contar caños)."""
    counts: dict[str, int] = {}
    for box in boxes:
        counts[box.label] = counts.get(box.label, 0) + 1
    return dict(sorted(counts.items()))
