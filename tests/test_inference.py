import numpy as np
import pytest
from PIL import Image

from revision_pipes.inference import INPUT_SIZE, Detector, decode, prepare

LABELS = ["porosidad", "fisura"]


def _logit(p):
    return float(np.log(p / (1 - p)))


def _raw(queries):
    """queries: lista de (probabilidad por clase, (cx, cy, w, h))."""
    logits = np.array([[_logit(p) for p in probs] for probs, _ in queries], dtype=np.float32)
    boxes = np.array([box for _, box in queries], dtype=np.float32)
    return logits[None], boxes[None]


class FakeSession:
    def __init__(self, outputs):
        self.outputs = outputs
        self.received = None

    def run(self, output_names, input_feed):
        self.received = input_feed
        return list(self.outputs)


def test_prepare_da_forma_y_rango_del_entrenamiento():
    x = prepare(Image.new("L", (300, 200), 255))
    assert x.shape == (1, 3, INPUT_SIZE, INPUT_SIZE)
    assert x.dtype == np.float32
    assert x.max() == pytest.approx(1.0)


def test_decode_convierte_a_pixeles_y_filtra_por_umbral():
    logits, boxes = _raw([
        ((0.9, 0.1), (0.5, 0.5, 0.2, 0.4)),
        ((0.2, 0.3), (0.1, 0.1, 0.1, 0.1)),  # debajo del umbral
    ])
    result = decode(logits, boxes, image_size=(200, 100), labels=LABELS, threshold=0.5)
    assert len(result) == 1
    box = result[0]
    assert box.label == "porosidad"
    assert box.score == pytest.approx(0.9, abs=1e-4)
    assert (box.x_min, box.y_min, box.x_max, box.y_max) == pytest.approx((80, 30, 120, 70))


def test_decode_ordena_por_confianza_y_elige_la_mejor_clase():
    logits, boxes = _raw([
        ((0.6, 0.1), (0.2, 0.2, 0.1, 0.1)),
        ((0.1, 0.95), (0.7, 0.7, 0.1, 0.1)),
    ])
    result = decode(logits, boxes, (100, 100), LABELS, threshold=0.5)
    assert [b.label for b in result] == ["fisura", "porosidad"]


def test_decode_recorta_recuadros_que_se_salen():
    logits, boxes = _raw([((0.9, 0.1), (0.98, 0.5, 0.2, 0.2))])
    (box,) = decode(logits, boxes, (100, 100), LABELS, threshold=0.5)
    assert box.x_max == 100


def test_decode_rechaza_cantidad_de_clases_incorrecta():
    logits, boxes = _raw([((0.9, 0.1), (0.5, 0.5, 0.1, 0.1))])
    with pytest.raises(ValueError, match="clases"):
        decode(logits, boxes, (100, 100), ["solo_una"], threshold=0.5)


def test_detector_usa_la_sesion_y_devuelve_recuadros():
    session = FakeSession(_raw([((0.1, 0.8), (0.5, 0.5, 0.5, 0.5))]))
    detector = Detector(session, LABELS, threshold=0.5)
    result = detector.predict(Image.new("RGB", (64, 32)))
    assert session.received["pixel_values"].shape == (1, 3, INPUT_SIZE, INPUT_SIZE)
    assert [b.label for b in result] == ["fisura"]


def test_detector_sin_hallazgos_devuelve_lista_vacia():
    session = FakeSession(_raw([((0.1, 0.1), (0.5, 0.5, 0.5, 0.5))]))
    assert Detector(session, LABELS, threshold=0.5).predict(Image.new("RGB", (64, 64))) == []


def test_umbral_invalido_da_error():
    with pytest.raises(ValueError):
        Detector(FakeSession(()), LABELS, threshold=1.5)
