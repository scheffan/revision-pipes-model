"""App de revisión remota de soldaduras · paso 1: analizar una imagen.

Dos entradas distintas, cada una con su modelo: radiografía (defectos internos) y foto del
cordón (superficie). Una foto nunca se convierte en radiografía.

La IA marca y prioriza; el inspector decide.

Para correrla:  streamlit run app/streamlit_app.py
Los modelos van en models/ (modelo_radiografias.onnx/.json y modelo_cordones.onnx/.json).
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import streamlit as st
from PIL import Image, UnidentifiedImageError

from revision_pipes.preprocessing import InvalidImageError, load_image, normalize, to_grayscale
from revision_pipes.review import BIEN, DEFECTO, REVISAR, classify, drop_nested, verdict

MODELS = Path(__file__).resolve().parents[1] / "models"
# Umbral alto provisorio: solo decide si un hallazgo se pinta rojo o amarillo, nunca lo oculta.
# Se calibrará con la precisión en validación de cada modelo.
DEFAULT_HIGH = 0.5
LEVEL_TEXT = {DEFECTO: "🔴 Posible defecto", REVISAR: "🟡 Revisar", BIEN: "🟢 Bien"}

MODULES = {
    "radiografias": {
        "tab": "Radiografía",
        "upload": "Subí una radiografía digital (PNG, JPG, TIFF o BMP)",
        "help": "Detecta indicaciones internas: porosidad, fisuras, escoria, falta de "
        "penetración y de fusión.",
    },
    "cordones": {
        "tab": "Foto del cordón",
        "upload": "Subí una foto del cordón de soldadura (PNG o JPG)",
        "help": "Revisa la superficie: marca el cordón bueno, el cordón malo y los defectos "
        "visibles. No ve defectos internos.",
    },
}


@st.cache_resource(show_spinner="Cargando el modelo…")
def load_detector(modulo: str):
    from revision_pipes.inference import Detector

    config = json.loads((MODELS / f"modelo_{modulo}.json").read_text(encoding="utf-8"))
    detector = Detector.from_file(str(MODELS / f"modelo_{modulo}.onnx"), config["labels"],
                                  config["umbral"])
    return detector, config


def model_available(modulo: str) -> bool:
    return (MODELS / f"modelo_{modulo}.onnx").exists() and (
        MODELS / f"modelo_{modulo}.json"
    ).exists()


def open_image(data: bytes) -> Image.Image:
    """Abre la imagen; las radiografías de 16 bits se llevan a 8 bits sin perder contraste."""
    try:
        image = Image.open(io.BytesIO(data))
        if image.mode in ("RGB", "RGBA", "L", "P"):
            return image.convert("RGB")
    except UnidentifiedImageError:
        pass
    gray = normalize(to_grayscale(load_image(data)))
    return Image.fromarray((gray * 255).astype(np.uint8)).convert("RGB")


def analyze(modulo: str) -> None:
    info = MODULES[modulo]
    st.caption(info["help"])
    if not model_available(modulo):
        st.info(f"Todavía no está cargado el modelo de {info['tab'].lower()} en `models/`.")
        return

    uploaded = st.file_uploader(info["upload"], type=["png", "jpg", "jpeg", "tif", "tiff", "bmp"],
                                key=f"up_{modulo}")
    if uploaded is None:
        return
    try:
        image = open_image(uploaded.getvalue())
    except (InvalidImageError, OSError) as error:
        st.error(f"No pude abrir la imagen: {error}")
        return

    detector, config = load_detector(modulo)
    with st.spinner("Analizando…"):
        boxes = drop_nested(detector.predict(image))
        findings = classify(boxes, config.get("umbral_alto", DEFAULT_HIGH))

    show_good = st.toggle("Mostrar zonas sanas", value=True, key=f"good_{modulo}")
    visible = [f for f in findings if show_good or f.level != BIEN]

    from revision_pipes.visualize import draw_findings

    left, right = st.columns([3, 2])
    with left:
        st.image(draw_findings(image, visible), width="stretch")
    with right:
        st.subheader(verdict(findings))
        levels = [f.level for f in findings]
        a, b, c = st.columns(3)
        a.metric("Posibles defectos", levels.count(DEFECTO))
        b.metric("Para revisar", levels.count(REVISAR))
        c.metric("Zonas sanas", levels.count(BIEN))
        if visible:
            st.dataframe(
                [
                    {"N.º": f.number, "Hallazgo": f.name, "Nivel": LEVEL_TEXT[f.level],
                     "Confianza": f"{f.box.score:.0%}"}
                    for f in visible
                ],
                hide_index=True,
                width="stretch",
            )
        st.caption(
            "La IA sugiere; no aprueba ni rechaza. Rojo: el modelo está seguro. "
            "Amarillo: duda, conviene mirarlo. Decide el inspector."
        )


st.set_page_config(page_title="Revisión de soldaduras", layout="wide")
st.title("Revisión remota de soldaduras")
st.caption("Detección automatizada para la revisión del inspector.")

for tab, modulo in zip(st.tabs([m["tab"] for m in MODULES.values()]), MODULES, strict=True):
    with tab:
        analyze(modulo)
