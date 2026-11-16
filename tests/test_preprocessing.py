import io

import numpy as np
import pytest
from PIL import Image

from revision_pipes.preprocessing import (
    DEFAULT_SIZE,
    InvalidImageError,
    load_image,
    normalize,
    preprocess,
    stretch_contrast,
    to_grayscale,
)


def _png_bytes(array: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, format="PNG")
    return buffer.getvalue()


def _gradient(height: int = 100, width: int = 120, max_value: int = 255, dtype=np.uint8):
    row = np.linspace(0, max_value, width)
    return np.tile(row, (height, 1)).astype(dtype)


# --- Salida del pipeline ---------------------------------------------------------------

def test_salida_tiene_forma_tipo_y_rango_esperados():
    out = preprocess(_png_bytes(_gradient()))
    assert out.shape == (DEFAULT_SIZE, DEFAULT_SIZE)
    assert out.dtype == np.float32
    assert out.min() >= 0.0 and out.max() <= 1.0


def test_tamano_configurable():
    out = preprocess(_png_bytes(_gradient()), size=128)
    assert out.shape == (128, 128)


def test_acepta_ruta_de_archivo(tmp_path):
    path = tmp_path / "placa.png"
    Image.fromarray(_gradient()).save(path)
    assert preprocess(path).shape == (DEFAULT_SIZE, DEFAULT_SIZE)


# --- Profundidad de bits ---------------------------------------------------------------

def test_imagen_de_16_bits_se_normaliza(tmp_path):
    path = tmp_path / "placa16.tif"
    Image.fromarray(_gradient(max_value=65535, dtype=np.uint16)).save(path)
    array = load_image(path)
    assert array.dtype == np.uint16
    out = preprocess(path)
    assert out.min() >= 0.0 and out.max() <= 1.0


def test_8_y_16_bits_de_la_misma_imagen_dan_resultados_equivalentes(tmp_path):
    img8 = _gradient()
    img16 = img8.astype(np.uint16) * 257  # misma imagen escalada a 16 bits
    path16 = tmp_path / "placa16.tif"
    Image.fromarray(img16).save(path16)
    out8 = preprocess(_png_bytes(img8))
    out16 = preprocess(path16)
    np.testing.assert_allclose(out8, out16, atol=1e-3)


def test_normalize_por_tipo_de_dato():
    assert normalize(np.array([[0, 255]], dtype=np.uint8)).tolist() == [[0.0, 1.0]]
    assert normalize(np.array([[0, 65535]], dtype=np.uint16)).tolist() == [[0.0, 1.0]]


def test_normalize_rechaza_valores_invalidos():
    with pytest.raises(InvalidImageError):
        normalize(np.array([[0.0, np.nan]], dtype=np.float32))


# --- Color a escala de grises ----------------------------------------------------------

@pytest.mark.parametrize("channels", [3, 4])
def test_color_se_convierte_a_un_canal(channels):
    array = np.zeros((50, 50, channels), dtype=np.uint8)
    assert to_grayscale(array).shape == (50, 50)


def test_imagen_rgb_gris_equivale_a_la_version_en_escala_de_grises():
    gray = _gradient()
    rgb = np.stack([gray] * 3, axis=-1)
    np.testing.assert_allclose(
        preprocess(_png_bytes(gray)), preprocess(_png_bytes(rgb)), atol=1e-2
    )


# --- Casos borde -----------------------------------------------------------------------

def test_imagen_uniforme_no_genera_nan():
    out = preprocess(_png_bytes(np.full((64, 64), 128, dtype=np.uint8)))
    assert np.all(np.isfinite(out))
    assert out.max() == 0.0


def test_stretch_contrast_usa_todo_el_rango():
    out = stretch_contrast(np.linspace(0.4, 0.6, 1000, dtype=np.float32))
    assert out.min() == pytest.approx(0.0, abs=1e-6)
    assert out.max() == pytest.approx(1.0, abs=1e-6)


def test_archivo_que_no_es_imagen_da_error_claro():
    with pytest.raises(InvalidImageError, match="No se pudo leer la imagen"):
        preprocess(b"esto no es una imagen")


def test_imagen_demasiado_chica_da_error_claro():
    with pytest.raises(InvalidImageError, match="demasiado chica"):
        preprocess(_png_bytes(np.zeros((10, 10), dtype=np.uint8)))


def test_archivo_inexistente_da_error():
    with pytest.raises(FileNotFoundError):
        preprocess("no_existe.png")
