"""Preprocesamiento de radiografías de soldaduras.

Todo lo que entra al modelo pasa por acá:

1. Se abre la imagen (ruta, bytes o archivo subido) y se valida.
2. Se pasa a escala de grises.
3. Se normaliza a valores entre 0 y 1, según la profundidad de bits
   (8 bits en fotos o escaneos, 16 bits en radiografía digital).
4. Se estira el contraste usando percentiles, porque las radiografías
   suelen ocupar una parte chica del rango disponible.
5. Se redimensiona al tamaño que espera el modelo (224x224 por defecto).
"""

from __future__ import annotations

import io
from os import PathLike
from typing import BinaryIO

import numpy as np
from PIL import Image, UnidentifiedImageError

MIN_SIDE = 32
DEFAULT_SIZE = 224

ImageSource = str | PathLike | bytes | BinaryIO


class InvalidImageError(ValueError):
    """La imagen no se puede usar: archivo dañado, formato no soportado o muy chica."""


def load_image(source: ImageSource) -> np.ndarray:
    """Abre una imagen y la devuelve como arreglo de numpy, sin modificar sus valores."""
    try:
        if isinstance(source, bytes):
            image = Image.open(io.BytesIO(source))
        else:
            image = Image.open(source)
        image.load()
    except FileNotFoundError:
        raise
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError(
            "No se pudo leer la imagen. Formatos aceptados: PNG, JPG, TIFF o BMP."
        ) from exc

    array = np.asarray(image)
    if array.ndim not in (2, 3):
        raise InvalidImageError(f"Forma de imagen no soportada: {array.shape}.")
    if min(array.shape[0], array.shape[1]) < MIN_SIDE:
        raise InvalidImageError(
            f"La imagen es demasiado chica ({array.shape[1]}x{array.shape[0]} px). "
            f"Mínimo: {MIN_SIDE} px por lado."
        )
    return array


def to_grayscale(array: np.ndarray) -> np.ndarray:
    """Convierte a un solo canal. Las imágenes RGB o RGBA usan pesos de luminancia."""
    if array.ndim == 2:
        return array
    channels = array.shape[2]
    if channels == 1:
        return array[:, :, 0]
    if channels in (3, 4):
        rgb = array[:, :, :3].astype(np.float64)
        gray = rgb @ np.array([0.299, 0.587, 0.114])
        return gray.astype(array.dtype) if np.issubdtype(array.dtype, np.integer) else gray
    raise InvalidImageError(f"Cantidad de canales no soportada: {channels}.")


def normalize(array: np.ndarray) -> np.ndarray:
    """Lleva los valores a float32 entre 0 y 1 según la profundidad de bits."""
    if array.dtype == np.uint8:
        out = array.astype(np.float32) / 255.0
    elif array.dtype == np.uint16:
        out = array.astype(np.float32) / 65535.0
    else:
        out = array.astype(np.float32)
        if not np.all(np.isfinite(out)):
            raise InvalidImageError("La imagen tiene valores inválidos (NaN o infinito).")
        low, high = float(out.min()), float(out.max())
        out = (out - low) / (high - low) if high > low else np.zeros_like(out)
    return np.clip(out, 0.0, 1.0)


def stretch_contrast(
    array: np.ndarray, low_pct: float = 1.0, high_pct: float = 99.0
) -> np.ndarray:
    """Estira el contraste entre dos percentiles. Una imagen uniforme queda en cero."""
    low, high = np.percentile(array, [low_pct, high_pct])
    if high - low < 1e-6:
        return np.zeros_like(array, dtype=np.float32)
    return np.clip((array - low) / (high - low), 0.0, 1.0).astype(np.float32)


def resize(array: np.ndarray, size: int = DEFAULT_SIZE) -> np.ndarray:
    """Redimensiona a size x size con interpolación bilineal."""
    image = Image.fromarray(array.astype(np.float32))  # float32 → modo "F" de Pillow
    resized = image.resize((size, size), resample=Image.Resampling.BILINEAR)
    return np.clip(np.asarray(resized, dtype=np.float32), 0.0, 1.0)


def preprocess(source: ImageSource, size: int = DEFAULT_SIZE) -> np.ndarray:
    """Pipeline completo: devuelve un arreglo float32 de (size, size) con valores en [0, 1]."""
    array = load_image(source)
    gray = to_grayscale(array)
    unit = normalize(gray)
    contrasted = stretch_contrast(unit)
    return resize(contrasted, size)
