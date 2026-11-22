"""Copia los modelos entrenados desde los .zip descargados de Kaggle a la carpeta models/.

Uso (desde la carpeta del proyecto):

    python scripts/instalar_modelos.py

Busca archivos .zip en notebooks/ y en la carpeta del proyecto; de cada uno toma
modelo_<modulo>.onnx y modelo_<modulo>.json, que es lo único que necesita la app.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
PATTERN = re.compile(r"(?:^|/)modelo_(\w+)\.(onnx|json)$")


def install(zips: list[Path]) -> dict[str, set[str]]:
    MODELS.mkdir(exist_ok=True)
    found: dict[str, set[str]] = {}
    for path in zips:
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                match = PATTERN.search(name)
                if not match:
                    continue
                modulo, ext = match.groups()
                (MODELS / f"modelo_{modulo}.{ext}").write_bytes(archive.read(name))
                found.setdefault(modulo, set()).add(ext)
    return found


def main() -> int:
    zips = sorted({*ROOT.glob("*.zip"), *(ROOT / "notebooks").glob("*.zip")})
    if not zips:
        print("No encontré ningún .zip en la carpeta del proyecto ni en notebooks/.")
        return 1
    found = install(zips)
    if not found:
        print("Los .zip no tienen modelos (modelo_<modulo>.onnx / .json).")
        return 1
    for modulo, exts in sorted(found.items()):
        estado = "listo ✅" if exts == {"onnx", "json"} else f"incompleto (solo {', '.join(exts)})"
        print(f"Modelo de {modulo}: {estado}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
