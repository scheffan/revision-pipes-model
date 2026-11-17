import pytest

from revision_pipes.annotations import (
    AnnotationError,
    Box,
    clean,
    from_coco,
    from_polygon,
    from_yolo,
)

CLASSES = ["defect", "good weld", "bad weld"]


# --- YOLO ------------------------------------------------------------------------------

def test_yolo_convierte_relativos_a_pixeles():
    boxes = from_yolo("0 0.5 0.5 0.2 0.4", image_width=200, image_height=100, class_names=CLASSES)
    assert boxes == [Box(80.0, 30.0, 120.0, 70.0, "defect")]


def test_yolo_ignora_lineas_vacias_y_lee_varias_clases():
    text = "0 0.5 0.5 0.1 0.1\n\n1 0.25 0.25 0.1 0.1\n"
    labels = [b.label for b in from_yolo(text, 100, 100, CLASSES)]
    assert labels == ["defect", "good weld"]


@pytest.mark.parametrize(
    "line, message",
    [
        ("0 0.5 0.5 0.2", "5 valores"),
        ("x 0.5 0.5 0.2 0.2", "no numéricos"),
        ("7 0.5 0.5 0.2 0.2", "desconocida"),
    ],
)
def test_yolo_lineas_invalidas_dan_error_claro(line, message):
    with pytest.raises(AnnotationError, match=message):
        from_yolo(line, 100, 100, CLASSES)


# --- COCO ------------------------------------------------------------------------------

def _coco():
    return {
        "categories": [{"id": 1, "name": "porosity"}, {"id": 2, "name": "crack"}],
        "images": [{"id": 10, "file_name": "a.png"}, {"id": 11, "file_name": "b.png"}],
        "annotations": [
            {"image_id": 10, "category_id": 1, "bbox": [5, 5, 10, 20]},
            {"image_id": 10, "category_id": 2, "bbox": [30, 30, 5, 5]},
        ],
    }


def test_coco_agrupa_por_imagen_y_convierte_ancho_alto():
    result = from_coco(_coco())
    assert result["a.png"][0] == Box(5, 5, 15, 25, "porosity")
    assert len(result["a.png"]) == 2


def test_coco_incluye_imagenes_sin_defectos():
    assert from_coco(_coco())["b.png"] == []


def test_coco_mal_formado_da_error():
    with pytest.raises(AnnotationError):
        from_coco({"images": []})


# --- Polígonos -------------------------------------------------------------------------

def test_poligono_da_el_recuadro_que_lo_contiene():
    box = from_polygon([(10, 20), (40, 25), (30, 60), (12, 50)], "crack")
    assert box == Box(10, 20, 40, 60, "crack")


def test_poligono_con_menos_de_tres_puntos_da_error():
    with pytest.raises(AnnotationError):
        from_polygon([(0, 0), (1, 1)], "crack")


# --- Limpieza --------------------------------------------------------------------------

def test_clean_recorta_a_la_imagen_y_descarta_recuadros_vacios():
    boxes = [
        Box(-10, -10, 50, 50, "defect"),     # se sale: se recorta
        Box(120, 120, 150, 150, "defect"),   # fuera de la imagen: queda sin tamaño
        Box(10, 10, 10.5, 30, "defect"),     # demasiado angosto
    ]
    assert clean(boxes, 100, 100) == [Box(0, 0, 50, 50, "defect")]


def test_area_y_dimensiones():
    box = Box(0, 0, 4, 5, "x")
    assert (box.width, box.height, box.area) == (4, 5, 20)
