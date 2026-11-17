import pytest

from revision_pipes.taxonomy import COMMON_CLASSES, normalize_label


@pytest.mark.parametrize(
    "original, esperado",
    [
        ("Lack Of Penetration", "falta de penetracion"),
        ("incomplete penetration", "falta de penetracion"),
        ("LOP", "falta de penetracion"),
        ("Tungsten Inclusion", "inclusion de tungsteno"),
        ("tungsten inclusion", "inclusion de tungsteno"),
        ("Slag Inclusions", "inclusion de escoria"),
        ("burn-through", "perforacion"),
        ("  Porosity ", "porosidad"),
        ("Good weld", "sin defecto"),
    ],
)
def test_alias_de_distintos_datasets_van_a_la_misma_clase(original, esperado):
    assert normalize_label(original) == esperado


def test_etiqueta_desconocida_queda_marcada_para_revisar():
    assert normalize_label("Spatter X") == "otro: Spatter X"


def test_clases_comunes_sin_duplicados():
    assert len(COMMON_CLASSES) == len(set(COMMON_CLASSES))
    assert "fisura" in COMMON_CLASSES


def test_clases_de_entrenamiento_agrupan_las_raras():
    from revision_pipes.taxonomy import TRAINING_CLASSES_RX, to_training_class

    assert to_training_class("porosidad") == "porosidad"
    assert to_training_class("perforacion") == "otro defecto"
    assert to_training_class("otro: algo raro") == "otro defecto"
    assert to_training_class("sin defecto") is None
    assert len(TRAINING_CLASSES_RX) == 6
