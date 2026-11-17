# Revisión remota de soldaduras con IA

Herramienta para que un inspector de soldaduras de ductos revise y apruebe radiografías **a distancia**. El técnico sube las placas desde la obra, un modelo de visión por computadora marca y ordena las zonas sospechosas, y el inspector decide.

> **La IA no aprueba nada: prioriza.** Está calibrada para que casi no se le escapen defectos, aunque eso implique algunas falsas alarmas. La decisión y la firma son siempre del inspector certificado.

## Estado

| Etapa | Qué incluye | Estado |
|---|---|---|
| 0. Base | Estructura, preprocesamiento, tests, CI | ✅ |
| 1. Datos | Descarga segura, duplicados, análisis exploratorio, split sin fuga | 🟡 cordones listo (4.621 imágenes → 993 fotos distintas); falta SWRD |
| 2. Modelo | Detector RT-DETR (Apache 2.0), métricas, umbral orientado a recall | ⏳ |
| 3. Visualización | Recuadros rojos (defecto), ámbar (cordón malo) y verdes (bien), con conteo | 🟡 módulo de dibujo listo |
| 4. App | Lote → priorización → revisión → decisión → informe PDF → auditoría | ⏳ |
| 5. QA | Historias de usuario, casos de prueba, tests e2e | 🟡 historias listas |
| 6. Difusión | Demo pública y documentación | ⏳ |

## Estructura

```
src/revision_pipes/   código del proyecto
app/                  app Streamlit
tests/                tests automáticos (pytest)
data/                 datasets (no se suben, ver data/README.md)
notebooks/            notebook de Kaggle (se genera con scripts/build_kaggle_notebook.py)
scripts/              utilidades del proyecto
docs/                 bitácora con capturas, licencias de datos y documentación QA
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

| Dataset | Qué aporta | Licencia |
|---|---|---|
| SWRD | Radiografías de soldaduras de costura con defectos marcados | Sin licencia publicada: uso de investigación y portfolio, sin redistribuir |
| Fotos de cordones (Roboflow) | Recuadros de cordón bueno, cordón malo y defecto | CC BY 4.0 y dominio público |
| GDXray (Welds) | Evaluación con otra fuente | Solo investigación y educación |

Las imágenes no se incluyen en el repo. Las copias aumentadas y las fotos repetidas entre datasets se agrupan para que ninguna quede a la vez en entrenamiento y en prueba. Detalle en [`docs/licencias-datos.md`](docs/licencias-datos.md).

## Bitácora

El proceso, etapa por etapa y con capturas, está en [`docs/bitacora.md`](docs/bitacora.md).
