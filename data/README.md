# Datos

Esta carpeta no se sube a GitHub (está en `.gitignore`), salvo este archivo.

| Dataset | Para qué se usa | Cómo se obtiene |
|---|---|---|
| RIAWELC | Entrenamiento y validación del clasificador (fisura, poro, falta de penetración, sin defecto) | Script de descarga (Etapa 1) |
| GDXray, serie Welds | Prueba de generalización con placas completas de otra fuente | Descarga manual desde el sitio oficial (Etapa 1) |

Por qué no se suben:
- **Licencias:** GDXray permite uso solo de investigación y educativo, y prohíbe redistribuirlo. Ver `docs/licencias-datos.md`.
- **Tamaño:** son varios GB.
- **Datos reales de clientes:** si en algún momento hay radiografías de obra, nunca pasan por el repo ni por la demo pública.
