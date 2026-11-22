import pytest
from PIL import Image

from revision_pipes.annotations import Box
from revision_pipes.review import BIEN, DEFECTO, REVISAR, classify, display_name, verdict
from revision_pipes.visualize import GREEN, RED, YELLOW, draw_findings


def _boxes():
    return [
        Box(10, 10, 40, 40, "Defect", 0.20),
        Box(50, 50, 90, 90, "Good Weld", 0.90),
        Box(5, 60, 30, 95, "porosidad", 0.80),
    ]


def test_clasifica_por_nivel_y_ordena_primero_lo_seguro():
    findings = classify(_boxes(), high_threshold=0.5)
    assert [f.level for f in findings] == [DEFECTO, REVISAR, BIEN]
    assert [f.number for f in findings] == [1, 2, 3]
    assert findings[0].box.label == "porosidad"


def test_cordon_bueno_nunca_es_defecto_aunque_tenga_puntaje_alto():
    (finding,) = classify([Box(0, 0, 10, 10, "Good Weld", 0.99)], high_threshold=0.5)
    assert finding.level == BIEN


def test_umbral_alto_invalido():
    with pytest.raises(ValueError):
        classify(_boxes(), high_threshold=1.5)


def test_nombres_para_mostrar():
    assert display_name("Bad Weld") == "Cordón malo"
    assert display_name("falta de penetracion") == "Falta de penetración"
    assert display_name("porosidad") == "Porosidad"


@pytest.mark.parametrize(
    "scores, expected",
    [
        ([0.9, 0.2], "1 posible defecto y 1 para revisar"),
        ([0.9, 0.8], "2 posibles defectos"),
        ([0.2], "Sin defectos claros · 1 zona para revisar"),
        ([], "Sin hallazgos"),
    ],
)
def test_resumen(scores, expected):
    boxes = [Box(0, 0, 10, 10, "fisura", s) for s in scores]
    assert verdict(classify(boxes, 0.5)) == expected


def test_colores_por_nivel():
    image = Image.new("RGB", (100, 100), (128, 128, 128))
    result = draw_findings(image, classify(_boxes(), 0.5))
    assert result.getpixel((5, 80)) == RED  # porosidad segura (borde izquierdo)
    assert result.getpixel((10, 30)) == YELLOW  # defecto dudoso
    assert result.getpixel((90, 88)) == GREEN  # cordón bueno


def test_quita_recuadros_encimados_de_la_misma_clase():
    from revision_pipes.review import drop_nested

    boxes = [
        Box(0, 0, 100, 100, "Bad Weld", 0.6),
        Box(10, 10, 60, 60, "Bad Weld", 0.4),  # adentro del anterior: se quita
        Box(10, 10, 60, 60, "Defect", 0.3),  # otra clase: se queda
        Box(90, 90, 150, 150, "Bad Weld", 0.5),  # apenas se toca: se queda
    ]
    kept = drop_nested(boxes)
    assert len(kept) == 3
    assert Box(10, 10, 60, 60, "Bad Weld", 0.4) not in kept


def test_si_el_grande_es_menos_seguro_queda_el_chico():
    from revision_pipes.review import drop_nested

    kept = drop_nested([Box(0, 0, 100, 100, "Bad Weld", 0.3), Box(10, 10, 60, 60, "Bad Weld", 0.6)])
    assert kept == [Box(10, 10, 60, 60, "Bad Weld", 0.6)]
