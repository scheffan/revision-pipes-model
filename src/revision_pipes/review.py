"""Lectura de los hallazgos para el inspector: qué es defecto, qué conviene revisar, qué está bien.

El modelo devuelve recuadros con un puntaje. Para no llenar la pantalla de rojo, cada hallazgo
se clasifica en un nivel:

- "defecto": un problema y el modelo está seguro (puntaje >= umbral alto).
- "revisar": un problema posible, pero con poca confianza. La IA lo señala; el inspector decide.
- "bien": zona sana (por ejemplo, "cordón bueno" en las fotos).

El umbral del modelo (el más bajo) se eligió para no perder defectos; el umbral alto solo cambia
cómo se muestra el hallazgo, nunca lo oculta.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from revision_pipes.annotations import Box

DEFECTO = "defecto"
REVISAR = "revisar"
BIEN = "bien"

# Nombres para mostrar en la app. Las clases de radiografías ya vienen en español.
DISPLAY_NAMES = {
    "Good Weld": "Cordón bueno",
    "Bad Weld": "Cordón malo",
    "Defect": "Defecto puntual",
    "inclusion de escoria": "Inclusión de escoria",
    "falta de penetracion": "Falta de penetración",
    "falta de fusion": "Falta de fusión",
}

GOOD_LABELS = {"Good Weld"}


def display_name(label: str) -> str:
    return DISPLAY_NAMES.get(label, label[:1].upper() + label[1:])


@dataclass(frozen=True)
class Finding:
    number: int
    box: Box
    level: str

    @property
    def name(self) -> str:
        return display_name(self.box.label)


def _area(b: Box) -> float:
    return max((b.x_max - b.x_min) * (b.y_max - b.y_min), 1e-9)


def _overlap(a: Box, b: Box) -> float:
    """Intersección sobre el área del recuadro más chico (1 = uno está entero dentro del otro)."""
    w = max(0.0, min(a.x_max, b.x_max) - max(a.x_min, b.x_min))
    h = max(0.0, min(a.y_max, b.y_max) - max(a.y_min, b.y_min))
    return w * h / min(_area(a), _area(b))


def drop_nested(boxes: Sequence[Box], min_inside: float = 0.8) -> list[Box]:
    """Quita recuadros encimados de la misma clase: si uno queda casi entero dentro del otro
    (en cualquier sentido), se conserva el más seguro.

    Solo afecta lo que se muestra: el modelo a veces marca el mismo cordón entero y además
    medio cordón, y en pantalla eso son tres recuadros encimados para un único hallazgo.
    """
    kept: list[Box] = []
    for box in sorted(boxes, key=lambda b: -(b.score or 0.0)):
        inside = any(k.label == box.label and _overlap(k, box) >= min_inside for k in kept)
        if not inside:
            kept.append(box)
    return kept


def classify(boxes: Sequence[Box], high_threshold: float) -> list[Finding]:
    """Ordena los hallazgos (primero los defectos seguros) y les asigna un nivel."""
    if not 0.0 <= high_threshold <= 1.0:
        raise ValueError("El umbral alto debe estar entre 0 y 1.")

    def level(box: Box) -> str:
        if box.label in GOOD_LABELS:
            return BIEN
        return DEFECTO if (box.score or 0.0) >= high_threshold else REVISAR

    order = {DEFECTO: 0, REVISAR: 1, BIEN: 2}
    ranked = sorted(boxes, key=lambda b: (order[level(b)], -(b.score or 0.0)))
    return [Finding(i, b, level(b)) for i, b in enumerate(ranked, start=1)]


def verdict(findings: Iterable[Finding]) -> str:
    """Resumen en una línea para la pantalla. Es una sugerencia: decide el inspector."""
    levels = [f.level for f in findings]
    n_def, n_rev = levels.count(DEFECTO), levels.count(REVISAR)
    if n_def:
        extra = f" y {n_rev} para revisar" if n_rev else ""
        return f"{n_def} posible{'s' if n_def > 1 else ''} defecto{'s' if n_def > 1 else ''}{extra}"
    if n_rev:
        return f"Sin defectos claros · {n_rev} zona{'s' if n_rev > 1 else ''} para revisar"
    return "Sin hallazgos"
