"""Regresión de métricas: si un modelo nuevo rinde menos que el piso acordado, el CI falla.

Los pisos están apenas por debajo de cada modelo vigente, para que un reentrenamiento no pueda
empeorar sin que nadie se entere.

- Radiografías: v2 con ventanas (18-nov-2026). La v1 queda en docs/metricas/radiografias_v1.json.
- Fotos de cordones: primera versión (22-nov-2026). Sus falsas alarmas en cordones sanos (38 %)
  son la línea de base a bajar; el techo de 40 % solo impide que empeoren.
"""

import json
from pathlib import Path

import pytest

METRICS_DIR = Path(__file__).resolve().parents[1] / "docs" / "metricas"

FLOORS = {
    "radiografias": {"map50": 0.62, "recall_por_placa": 0.94},
    "cordones": {"map50": 0.52, "recall_por_placa": 0.95},
}
CLASS_RECALL_FLOORS = {
    "radiografias": {
        "porosidad": 0.76,
        "fisura": 0.75,
        "inclusion de escoria": 0.62,
        "falta de penetracion": 0.82,
    },
    "cordones": {"Bad Weld": 0.77, "Defect": 0.62},
}


def load(modulo):
    return json.loads((METRICS_DIR / f"{modulo}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "modulo, name, floor", [(m, n, f) for m, fl in FLOORS.items() for n, f in fl.items()]
)
def test_metrica_global_no_baja_del_piso(modulo, name, floor):
    assert load(modulo)[name] >= floor


@pytest.mark.parametrize(
    "modulo, label, floor",
    [(m, lbl, f) for m, fl in CLASS_RECALL_FLOORS.items() for lbl, f in fl.items()],
)
def test_recall_por_clase_no_baja_del_piso(modulo, label, floor):
    assert load(modulo)["por_clase"][label]["recall"] >= floor


@pytest.mark.parametrize("modulo", FLOORS)
def test_onnx_verificado(modulo):
    assert load(modulo)["onnx"]["mismos_hallazgos_que_pytorch"] is True


def test_radiografias_falsas_alarmas_en_zonas_sanas_no_superan_el_15_por_ciento():
    m = load("radiografias")
    assert m["zonas_sanas_con_falsa_alarma"] / m["zonas_sanas_prueba"] <= 0.15


def test_cordones_falsas_alarmas_en_fotos_sanas_no_empeoran():
    m = load("cordones")
    assert m["imagenes_sin_defecto_con_falsa_alarma"] / m["imagenes_sin_defecto_prueba"] <= 0.40


def test_portero_distingue_los_tipos_de_imagen():
    m = load("portero")
    assert m["exactitud"] >= 0.99
    assert m["por_clase"]["radiografia"]["exactitud"] >= 0.99
    assert m["por_clase"]["foto_cordon"]["exactitud"] >= 0.98
    # Una radiografía de tórax nunca debería pasar como radiografía de soldadura
    assert m["torax_tomadas_por_radiografia_de_soldadura"] == 0
    assert m["onnx"]["mismos_hallazgos_que_pytorch"] is True


@pytest.mark.parametrize("modulo", ["radiografias", "cordones"])
def test_rojo_calibrado_acierta_al_menos_8_de_cada_10_en_prueba(modulo):
    cal = json.loads((METRICS_DIR / "calibracion.json").read_text(encoding="utf-8"))[modulo]
    models = METRICS_DIR.parents[1] / "models"
    config = json.loads((models / f"modelo_{modulo}.json").read_text(encoding="utf-8"))
    assert config["umbral_alto"] == cal["umbral_alto"]  # la app usa el corte calibrado
    assert config["umbral"] <= config["umbral_alto"] <= 1
    assert cal["prueba"]["precision_rojos"] >= 0.80
