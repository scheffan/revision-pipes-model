"""Separación en entrenamiento, validación y prueba sin fuga de datos.

Si dos recortes salen de la misma placa radiográfica y uno cae en entrenamiento
y otro en prueba, el modelo "ya vio" esa placa y las métricas salen infladas.
Por eso se separa por grupo (la placa de origen), no por imagen suelta.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from typing import TypeVar

T = TypeVar("T")


def split_by_group(
    items: Sequence[T],
    group_of: Callable[[T], str],
    ratios: tuple[float, float, float] = (0.7, 0.15, 0.15),
    seed: int = 42,
) -> dict[str, list[T]]:
    """Reparte los grupos completos entre train, val y test según las proporciones.

    Es reproducible: con la misma semilla siempre da la misma separación.
    """
    if len(ratios) != 3 or any(r < 0 for r in ratios) or abs(sum(ratios) - 1.0) > 1e-6:
        raise ValueError("Las proporciones deben ser tres valores no negativos que sumen 1.")

    groups: dict[str, list[T]] = {}
    for item in items:
        groups.setdefault(group_of(item), []).append(item)

    names = sorted(groups)
    random.Random(seed).shuffle(names)

    n = len(names)
    n_train = round(n * ratios[0])
    n_val = round(n * ratios[1])
    assignment = {
        "train": names[:n_train],
        "val": names[n_train : n_train + n_val],
        "test": names[n_train + n_val :],
    }
    return {split: [item for g in gs for item in groups[g]] for split, gs in assignment.items()}
