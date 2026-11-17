from PIL import Image

from revision_pipes.annotations import Box
from revision_pipes.visualize import AMBER, GREEN, RED, color_for, draw_boxes, summarize


def test_colores_por_tipo_de_etiqueta():
    assert color_for("Good Weld") == GREEN
    assert color_for("bad weld") == AMBER
    assert color_for("porosity") == RED
    assert color_for("crack") == RED


def test_dibuja_sin_modificar_la_original():
    original = Image.new("L", (100, 100), color=0)
    result = draw_boxes(original, [Box(10, 10, 60, 60, "crack")], show_numbers=False)
    assert original.getpixel((10, 10)) == 0
    assert result.mode == "RGB"
    assert result.getpixel((10, 10)) == RED


def test_recuadro_sano_se_dibuja_en_verde():
    result = draw_boxes(Image.new("L", (100, 100)), [Box(20, 20, 80, 80, "good weld")],
                        show_numbers=False)
    assert result.getpixel((20, 50)) == GREEN


def test_sin_recuadros_devuelve_la_imagen_igual():
    original = Image.new("RGB", (50, 50), color=(5, 5, 5))
    assert draw_boxes(original, []).tobytes() == original.tobytes()


def test_summarize_cuenta_por_etiqueta():
    boxes = [Box(0, 0, 5, 5, "pipe")] * 3 + [Box(0, 0, 5, 5, "crack")]
    assert summarize(boxes) == {"crack": 1, "pipe": 3}
