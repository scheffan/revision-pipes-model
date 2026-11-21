"""Regresión de métricas: si un modelo nuevo rinde menos que el piso acordado, el CI falla.

Los pisos están apenas por debajo del modelo vigente (v2 con ventanas, 18-nov-2026), para que
un reentrenamiento no pueda empeorar sin que nadie se entere. La v1 queda como referencia
en docs/metricas/radiografias_v1.json.
"""

import json
from pathlib import Path

import pytest

METRICS = Path(__file__).resolve().parents[1] / "docs" / "metricas" / "radiografias.json"
FLOORS = {"map50": 0.62, "recall_por_placa": 0.94}
CLASS_RECALL_FLOORS = {
    "porosidad": 0.76,
    "fisura": 0.75,
    "inclusion de escoria": 0.62,
    "falta de penetracion": 0.82,
}


@pytest.fixture(scope="module")
def metrics():
    return json.loads(METRICS.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name, floor", FLOORS.items())
def test_metrica_global_no_baja_del_piso(metrics, name, floor):
    assert metrics[name] >= floor


@pytest.mark.parametrize("label, floor", CLASS_RECALL_FLOORS.items())
def test_recall_por_clase_no_baja_del_piso(metrics, label, floor):
    assert metrics["por_clase"][label]["recall"] >= floor


def test_onnx_verificado(metrics):
    assert metrics["onnx"]["mismos_hallazgos_que_pytorch"] is True


def test_falsas_alarmas_en_zonas_sanas_no_superan_el_15_por_ciento(metrics):
    assert metrics["zonas_sanas_con_falsa_alarma"] / metrics["zonas_sanas_prueba"] <= 0.15
