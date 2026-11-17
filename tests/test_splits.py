import pytest

from revision_pipes.splits import split_by_group


def _items():
    # 20 placas, 5 recortes por placa
    return [(f"placa{p:02d}", i) for p in range(20) for i in range(5)]


def _group(item):
    return item[0]


def test_ninguna_placa_aparece_en_dos_conjuntos():
    splits = split_by_group(_items(), _group)
    groups = {name: {_group(i) for i in items} for name, items in splits.items()}
    assert not groups["train"] & groups["val"]
    assert not groups["train"] & groups["test"]
    assert not groups["val"] & groups["test"]


def test_no_se_pierde_ni_se_duplica_ningun_item():
    items = _items()
    splits = split_by_group(items, _group)
    combined = [i for part in splits.values() for i in part]
    assert sorted(combined) == sorted(items)


def test_respeta_las_proporciones_por_grupo():
    splits = split_by_group(_items(), _group, ratios=(0.7, 0.15, 0.15))
    placas = {k: len({_group(i) for i in v}) for k, v in splits.items()}
    assert placas == {"train": 14, "val": 3, "test": 3}


def test_es_reproducible_con_la_misma_semilla():
    assert split_by_group(_items(), _group, seed=7) == split_by_group(_items(), _group, seed=7)


def test_otra_semilla_da_otra_separacion():
    assert split_by_group(_items(), _group, seed=1) != split_by_group(_items(), _group, seed=2)


@pytest.mark.parametrize("ratios", [(0.5, 0.5, 0.5), (1.2, -0.1, -0.1), (0.5, 0.5)])
def test_proporciones_invalidas_dan_error(ratios):
    with pytest.raises(ValueError):
        split_by_group(_items(), _group, ratios=ratios)
