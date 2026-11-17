"""Formato común de anotaciones (recuadros) para todos los datasets.

Cada dataset trae los recuadros en un formato distinto:
- YOLO: un .txt por imagen, con valores relativos (0 a 1) al tamaño de la imagen.
- COCO: un .json con [x, y, ancho, alto] en píxeles.
- Polígonos (SWRD): lista de puntos que rodean el defecto.

Este módulo los lleva todos a `Box`, en píxeles absolutos (x_min, y_min, x_max, y_max),
para que el resto del proyecto no dependa del formato de origen.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

MIN_BOX_SIDE = 1.0


class AnnotationError(ValueError):
    """Una anotación no se puede interpretar."""


@dataclass(frozen=True)
class Box:
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    label: str

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @property
    def area(self) -> float:
        return max(self.width, 0.0) * max(self.height, 0.0)

    def clip(self, image_width: int, image_height: int) -> Box:
        """Recorta el recuadro para que no se salga de la imagen."""
        return Box(
            x_min=min(max(self.x_min, 0.0), image_width),
            y_min=min(max(self.y_min, 0.0), image_height),
            x_max=min(max(self.x_max, 0.0), image_width),
            y_max=min(max(self.y_max, 0.0), image_height),
            label=self.label,
        )

    def is_valid(self) -> bool:
        return self.width >= MIN_BOX_SIDE and self.height >= MIN_BOX_SIDE


def from_yolo(
    text: str, image_width: int, image_height: int, class_names: Sequence[str]
) -> list[Box]:
    """Lee un .txt de YOLO: `clase x_centro y_centro ancho alto` (relativos, 0 a 1)."""
    boxes = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        parts = line.split()
        if not parts:
            continue
        if len(parts) != 5:
            raise AnnotationError(f"Línea {line_number}: se esperaban 5 valores, hay {len(parts)}.")
        try:
            class_id = int(parts[0])
            xc, yc, w, h = (float(value) for value in parts[1:])
        except ValueError as exc:
            raise AnnotationError(f"Línea {line_number}: valores no numéricos.") from exc
        if not 0 <= class_id < len(class_names):
            raise AnnotationError(f"Línea {line_number}: clase {class_id} desconocida.")
        boxes.append(
            Box(
                x_min=(xc - w / 2) * image_width,
                y_min=(yc - h / 2) * image_height,
                x_max=(xc + w / 2) * image_width,
                y_max=(yc + h / 2) * image_height,
                label=class_names[class_id],
            )
        )
    return boxes


def from_coco(coco: dict) -> dict[str, list[Box]]:
    """Lee un diccionario COCO y devuelve los recuadros agrupados por nombre de archivo."""
    try:
        categories = {c["id"]: c["name"] for c in coco["categories"]}
        images = {img["id"]: img["file_name"] for img in coco["images"]}
        result: dict[str, list[Box]] = {name: [] for name in images.values()}
        for ann in coco["annotations"]:
            x, y, w, h = ann["bbox"]
            result[images[ann["image_id"]]].append(
                Box(x, y, x + w, y + h, categories[ann["category_id"]])
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise AnnotationError(f"Archivo COCO mal formado: {exc}") from exc
    return result


def from_polygon(points: Iterable[Sequence[float]], label: str) -> Box:
    """Convierte un polígono (lista de puntos x, y) en el recuadro que lo contiene."""
    points = list(points)
    if len(points) < 3:
        raise AnnotationError("Un polígono necesita al menos 3 puntos.")
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    return Box(min(xs), min(ys), max(xs), max(ys), label)


def clean(boxes: Iterable[Box], image_width: int, image_height: int) -> list[Box]:
    """Recorta los recuadros a la imagen y descarta los que quedan sin tamaño."""
    clipped = (box.clip(image_width, image_height) for box in boxes)
    return [box for box in clipped if box.is_valid()]
