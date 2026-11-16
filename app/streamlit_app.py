"""App de revisión remota de soldaduras (esqueleto de la Etapa 0).

Por ahora solo muestra cómo queda una radiografía después del preprocesamiento.
El modelo, la priorización y el flujo del inspector llegan en las etapas siguientes.

Para correrla:  streamlit run app/streamlit_app.py
"""

import streamlit as st

from revision_pipes.preprocessing import InvalidImageError, load_image, preprocess

st.set_page_config(page_title="Revisión de soldaduras", layout="wide")

st.title("Revisión remota de soldaduras")
st.caption(
    "La IA prioriza las radiografías. El inspector revisa y decide. "
    "Versión en desarrollo: todavía no hay modelo."
)

uploaded = st.file_uploader(
    "Subí una radiografía (PNG, JPG, TIFF o BMP)",
    type=["png", "jpg", "jpeg", "tif", "tiff", "bmp"],
)

if uploaded is not None:
    data = uploaded.getvalue()
    try:
        original = load_image(data)
        processed = preprocess(data)
    except InvalidImageError as error:
        st.error(str(error))
    else:
        left, right = st.columns(2)
        with left:
            st.subheader("Original")
            st.image(data, width="stretch")
            st.write(f"{original.shape[1]}×{original.shape[0]} px · {original.dtype}")
        with right:
            st.subheader("Preprocesada (entrada del modelo)")
            st.image(processed, clamp=True, width="stretch")
            st.write(f"{processed.shape[1]}×{processed.shape[0]} px · valores entre 0 y 1")
