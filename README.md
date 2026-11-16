# Revisión remota de soldaduras con IA

Herramienta para que un inspector de soldaduras de ductos revise y apruebe radiografías **a distancia**. El técnico sube las placas desde la obra, un modelo de visión por computadora marca y ordena las zonas sospechosas, y el inspector decide.

> **La IA no aprueba nada: prioriza.** Está calibrada para que casi no se le escapen defectos, aunque eso implique algunas falsas alarmas. La decisión y la firma son siempre del inspector certificado.

## Estado

| Etapa | Qué incluye | Estado |
|---|---|---|
| 0. Base | Estructura, preprocesamiento, tests, CI | ✅ |
| 1. Datos | Descarga, análisis exploratorio, split sin fuga de datos | ⏳ |
| 2. Modelo | Transfer learning, métricas, umbral orientado a recall | ⏳ |
| 3. Localización | Mapa de calor y recuadros sobre la placa completa | ⏳ |
| 4. App | Lote → priorización → revisión → decisión → informe PDF → auditoría | ⏳ |
| 5. QA | Historias de usuario, casos de prueba, tests e2e | 🟡 historias listas |
| 6. Difusión | Demo pública y documentación | ⏳ |

## Estructura

```
src/revision_pipes/   código del proyecto
app/                  app Streamlit
tests/                tests automáticos (pytest)
data/                 datasets (no se suben, ver data/README.md)
docs/                 licencias de datos y documentación QA
```

## Cómo correrlo

Requiere Python 3.10 o superior.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    ·    Linux/Mac: source .venv/bin/activate
pip install -e ".[dev,app]"

pytest                               # tests
streamlit run app/streamlit_app.py   # app
```

## Datos

Se entrena con datasets públicos de radiografías de soldaduras (RIAWELC) y se evalúa la generalización con otra fuente (GDXray). Las imágenes no se incluyen en el repo por licencia. Detalle en [`docs/licencias-datos.md`](docs/licencias-datos.md).
