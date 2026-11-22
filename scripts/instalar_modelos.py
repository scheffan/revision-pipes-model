"""Copia los modelos entrenados desde los .zip descargados de Kaggle a la carpeta models/.

Uso (desde la carpeta del proyecto):

    python scripts/instalar_modelos.py

Busca en notebooks/ y en la carpeta del proyecto los modelo_<modulo>.onnx, sueltos o dentro de
los .zip descargados de Kaggle, y los copia a models/. Las configuraciones (modelo_<modulo>.json)
ya vienen en el repo; solo se copian desde Kaggle si faltan.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
PATTERN = re.compile(r"(?:^|/)modelo_(\w+)\.(onnx|json)$")


def _store(modulo: str, ext: str, read) -> bool:
    target = MODELS / f"modelo_{modulo}.{ext}"
    if ext == "json" and target.exists():
        return True  # la configuración del repo manda
    target.write_bytes(read())
    return True


def install(sources: list[Path]) -> dict[str, set[str]]:
    MODELS.mkdir(exist_ok=True)
    found: dict[str, set[str]] = {}
    for path in sources:
        if path.suffix == ".zip":
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    match = PATTERN.search(name)
                    if match and _store(*match.groups(), lambda n=name: archive.read(n)):
                        found.setdefault(match.group(1), set()).add(match.group(2))
        else:
            match = PATTERN.search(path.name)
            if match and _store(*match.groups(), path.read_bytes):
                found.setdefault(match.group(1), set()).add(match.group(2))
    for config in MODELS.glob("modelo_*.json"):
        found.setdefault(config.stem.removeprefix("modelo_"), set()).add("json")
    return found


def main() -> int:
    folders = [ROOT, ROOT / "notebooks"]
    patterns = ("*.zip", "modelo_*.onnx")
    sources = sorted({p for f in folders for pat in patterns for p in f.glob(pat)})
    if not sources:
        print("No encontré modelos (.zip o modelo_*.onnx) en el proyecto ni en notebooks.")
        return 1
    found = install(sources)
    for modulo, exts in sorted(found.items()):
        estado = "listo ✅" if exts == {"onnx", "json"} else "falta el .onnx (bajalo de Kaggle)"
        print(f"Modelo de {modulo}: {estado}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
