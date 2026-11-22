import importlib.util
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "instalar_modelos.py"


def _load(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("instalar_modelos", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "MODELS", tmp_path / "models")
    return module


def test_copia_solo_onnx_y_json_de_cada_modulo(tmp_path, monkeypatch):
    module = _load(tmp_path, monkeypatch)
    zip_path = tmp_path / "results.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("modelo_cordones.onnx", b"onnx")
        z.writestr("modelo_cordones.json", "{}")
        z.writestr("modelo_cordones/config.json", "{}")  # carpeta de PyTorch: no hace falta
        z.writestr("curvas_cordones.png", b"png")
    found = module.install([zip_path])
    assert found == {"cordones": {"onnx", "json"}}
    assert sorted(p.name for p in (tmp_path / "models").iterdir()) == [
        "modelo_cordones.json",
        "modelo_cordones.onnx",
    ]


def test_toma_onnx_suelto_y_no_pisa_la_configuracion_del_repo(tmp_path, monkeypatch):
    module = _load(tmp_path, monkeypatch)
    models = tmp_path / "models"
    models.mkdir()
    (models / "modelo_radiografias.json").write_text('{"repo": true}')
    onnx = tmp_path / "modelo_radiografias.onnx"
    onnx.write_bytes(b"onnx")
    zip_path = tmp_path / "results.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("modelo_radiografias.json", '{"kaggle": true}')
    found = module.install([onnx, zip_path])
    assert found == {"radiografias": {"onnx", "json"}}
    assert (models / "modelo_radiografias.json").read_text() == '{"repo": true}'
    assert (models / "modelo_radiografias.onnx").read_bytes() == b"onnx"
