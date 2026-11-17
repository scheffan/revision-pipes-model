"""Nombres comunes para los tipos de defecto en radiografías.

Cada dataset nombra los defectos a su manera ("Lack Of Penetration", "incomplete penetration",
"LOP", "Tungsten Inclusion" y "tungsten inclusion" en el mismo dataset...). Para entrenar un
solo modelo hace falta una lista única de clases, con nombres en español para la app.
"""

from __future__ import annotations

import re

# Nombre normalizado de entrada (minúsculas, sin signos) -> clase común
ALIASES = {
    "crack": "fisura",
    "cracks": "fisura",
    "porosity": "porosidad",
    "pore": "porosidad",
    "blowhole": "porosidad",
    "slag": "inclusion de escoria",
    "slag inclusion": "inclusion de escoria",
    "slag inclusions": "inclusion de escoria",
    "lack of fusion": "falta de fusion",
    "incomplete fusion": "falta de fusion",
    "lof": "falta de fusion",
    "lack of penetration": "falta de penetracion",
    "incomplete penetration": "falta de penetracion",
    "lop": "falta de penetracion",
    "non penetration": "falta de penetracion",
    "undercut": "socavadura",
    "undarcut": "socavadura",
    "burn through": "perforacion",
    "burnthrough": "perforacion",
    "tungsten inclusion": "inclusion de tungsteno",
    "excessive reinforcement": "sobremonta excesiva",
    "inadequate reinforcement": "sobremonta insuficiente",
    "root concavity": "concavidad de raiz",
    "good weld": "sin defecto",
    "no defect": "sin defecto",
}

COMMON_CLASSES = sorted(set(ALIASES.values()))


def _key(label: str) -> str:
    return re.sub(r"[^a-z]+", " ", label.lower()).strip()


def normalize_label(label: str) -> str:
    """Devuelve la clase común. Si el nombre no se conoce, devuelve 'otro: <original>'
    para que aparezca en el análisis y se pueda decidir qué hacer con él."""
    return ALIASES.get(_key(label), f"otro: {label.strip()}")
