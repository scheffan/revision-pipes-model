# Bitácora del proyecto

Registro de cada etapa con capturas. Es la base para el README público, la tarjeta del portfolio (ES/EN) y el proyecto en LinkedIn.

## Capturas pendientes por etapa

| Etapa | Captura | Para |
|---|---|---|
| 0 | Tests pasando en la PC local | README, LinkedIn ✅ |
| 0 | CI en verde en GitHub | README |
| 1 | Ejemplos de cada dataset con sus recuadros | README, portfolio 🟡 cordones listo, falta SWRD |
| 1 | Gráfico de cantidad de imágenes por clase | README, LinkedIn 🟡 cordones listo |
| 2 | Curvas de entrenamiento y matriz de confusión | README |
| 3 | Radiografía con defectos marcados en rojo y zonas sanas en verde | Portada del portfolio y LinkedIn |
| 4 | App: lote ordenado por prioridad, revisión, informe PDF | Portfolio, LinkedIn |
| 5 | Tests e2e pasando | README |

---

## Etapa 0 · Base (16-nov-2026)

**Qué se hizo:** estructura del repo, primer módulo real (preprocesamiento de radiografías de 8 y 16 bits), 15 tests automáticos, esqueleto de la app en Streamlit y CI en GitHub Actions.

**Decisiones:**
- Repo privado; la vitrina pública va aparte (README público y demo).
- Los datasets no se suben al repo, por licencia y tamaño.
- La IA prioriza, no aprueba: la decisión es del inspector certificado.

![Tests pasando en la PC local](capturas/etapa0-tests-locales.png)

**Resultado:** 15 tests pasando en la PC local y en el CI de GitHub.

---

## Etapa 1 · Datos (16-nov-2026, primera corrida en Kaggle)

**Qué se hizo:** notebook de Kaggle que baja los datasets, descarta todo lo que no sea imagen o etiqueta, convierte los recuadros a un formato común, agrupa copias y duplicados, separa los conjuntos sin fuga y dibuja ejemplos.

**Hallazgo clave: muchas imágenes, pocas fotos distintas.**

| Dataset | Imágenes | Originales por nombre |
|---|---|---|
| Cordones CC BY 4.0 (Roboflow) | 3.621 | 1.299 |
| Cordones dominio público (Roboflow) | 1.000 | 703 |
| **Total después de detectar duplicados por contenido** | **4.621** | **993 fotos distintas** |

El dataset grande infla su tamaño con copias espejadas y rotadas, y los dos datasets comparten fotos. Si se separara por imagen suelta, la misma foto (o su copia rotada) caería en entrenamiento y en prueba, y las métricas saldrían infladas. Se separó por grupo de foto: 3.255 imágenes para entrenamiento, 687 para validación y 679 para prueba, y una verificación automática confirma que ningún grupo aparece en dos conjuntos.

Nota: el umbral de parecido es estricto a propósito. Puede juntar algunas fotos distintas pero muy similares, lo que hace la separación más conservadora, nunca más optimista.

![Recuadros por clase](capturas/etapa1-cordones-clases.png)

Recuadros totales: 13.670 (Good Weld 5.485, Defect 4.928, Bad Weld 3.257), incluidas las copias aumentadas.

![Ejemplos con recuadros: rojo = defecto, ámbar = cordón malo, verde = cordón bueno](capturas/etapa1-cordones-recuadros.png)

*Imágenes: datasets "Welding_Defects" (Roboflow Universe, CC BY 4.0) y "welding defects detection" (Roboflow Universe, dominio público).*

**Pendiente:** las radiografías SWRD no se pudieron bajar porque Google Drive limita las descargas de archivos muy pedidos. Solución: subir el zip a Kaggle como dataset privado; el notebook ya lo detecta solo.
