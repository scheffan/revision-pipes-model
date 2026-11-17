import pytest

from revision_pipes.annotations import Box, iou
from revision_pipes.metrics import choose_threshold, image_recall, per_class


def gt(x, label="fisura"):
    return Box(x, 0, x + 10, 10, label)


def pred(x, score, label="fisura"):
    return Box(x, 0, x + 10, 10, label, score)


# --- IoU -------------------------------------------------------------------------------

def test_iou_casos_basicos():
    a = Box(0, 0, 10, 10, "x")
    assert iou(a, a) == 1.0
    assert iou(a, Box(20, 20, 30, 30, "x")) == 0.0
    assert iou(a, Box(5, 0, 15, 10, "x")) == pytest.approx(50 / 150)


# --- Recall por placa ------------------------------------------------------------------

def test_recall_por_placa_ignora_placas_sin_defectos():
    truths = [[gt(0)], [gt(0)], []]
    preds = [[pred(0, 0.9)], [], [pred(0, 0.9)]]
    assert image_recall(preds, truths, threshold=0.5) == 0.5


def test_recall_por_placa_respeta_el_umbral():
    truths = [[gt(0)], [gt(0)]]
    preds = [[pred(0, 0.9)], [pred(0, 0.3)]]
    assert image_recall(preds, truths, 0.5) == 0.5
    assert image_recall(preds, truths, 0.2) == 1.0


# --- Elección del umbral ---------------------------------------------------------------

def test_elige_el_umbral_mas_alto_que_cumple_el_recall():
    truths = [[gt(0)]] * 4
    preds = [[pred(0, 0.9)], [pred(0, 0.8)], [pred(0, 0.6)], [pred(0, 0.32)]]
    assert choose_threshold(preds, truths, target_recall=1.0) == 0.3
    assert choose_threshold(preds, truths, target_recall=0.75) == 0.6


def test_si_ningun_umbral_alcanza_devuelve_el_minimo():
    truths = [[gt(0)], [gt(0)]]
    preds = [[pred(0, 0.9)], []]
    assert choose_threshold(preds, truths, target_recall=1.0) == 0.05


# --- Por clase -------------------------------------------------------------------------

def test_por_clase_cuenta_aciertos_falsas_alarmas_y_perdidos():
    truths = [[gt(0), gt(50, "porosidad")]]
    preds = [[pred(1, 0.9), pred(100, 0.8), pred(50, 0.7, "fisura")]]
    m = per_class(preds, truths, threshold=0.5)
    assert (m["fisura"].true_positives, m["fisura"].false_positives) == (1, 2)
    assert m["porosidad"].false_negatives == 1
    assert m["fisura"].recall == 1.0
    assert m["fisura"].precision == pytest.approx(1 / 3)


def test_un_recuadro_real_no_se_cuenta_dos_veces():
    m = per_class([[pred(0, 0.9), pred(0, 0.8)]], [[gt(0)]], threshold=0.5)
    assert (m["fisura"].true_positives, m["fisura"].false_positives) == (1, 1)


def test_metricas_sin_casos_no_dividen_por_cero():
    m = per_class([[]], [[]], threshold=0.5)
    assert m == {}
