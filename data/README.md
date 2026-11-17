# Datos

Esta carpeta no se sube a GitHub (está en `.gitignore`), salvo este archivo.

| Dataset | Para qué se usa | Cómo se obtiene |
|---|---|---|
| Radiografías "weld" y "weld data" (Roboflow) | Detección de defectos en radiografías | Notebook de Kaggle (`notebooks/`) |
| Fotos de cordones (Roboflow) | Cordón bueno / malo / defecto en fotos | Notebook de Kaggle |
| GDXray (Welds) | Evaluación con otra fuente | Descarga manual (más adelante) |
| SWRD | En pausa: 116 GB y sin licencia publicada | — |

Por qué no se suben:
- **Licencias:** GDXray permite uso solo de investigación y educativo, y prohíbe redistribuirlo. Ver `docs/licencias-datos.md`.
- **Tamaño:** son varios GB.
- **Datos reales de clientes:** si en algún momento hay radiografías de obra, nunca pasan por el repo ni por la demo pública.
