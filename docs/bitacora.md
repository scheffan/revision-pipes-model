# Bitácora del proyecto

Registro de cada etapa con capturas. Es la base para el README público, la tarjeta del portfolio (ES/EN) y el proyecto en LinkedIn.

## Capturas pendientes por etapa

| Etapa | Captura | Para |
|---|---|---|
| 0 | Tests pasando en la PC local | README, LinkedIn ✅ |
| 0 | CI en verde en GitHub | README |
| 1 | Ejemplos de cada dataset con sus recuadros | README, portfolio ✅ |
| 1 | Gráfico de cantidad de imágenes por clase | README, LinkedIn ✅ |
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

Recuadros totales: 13.670 (Good Weld 5.485, Defect 4.928, Bad Weld 3.257), incluidas las copias aumentadas.

![Ejemplos con recuadros: rojo = defecto, ámbar = cordón malo, verde = cordón bueno](capturas/etapa1-cordones-recuadros.png)

*Imágenes: datasets "Welding_Defects" (Roboflow Universe, CC BY 4.0) y "welding defects detection" (Roboflow Universe, dominio público).*

**SWRD descartado por ahora:** el zip pesa 116 GB y no tiene licencia publicada. Se reemplazó por dos datasets de radiografías de Roboflow con licencia CC BY 4.0.

### Segunda corrida (17-nov-2026): radiografías

| Dataset | Imágenes | Licencia |
|---|---|---|
| "weld" (Roboflow, versión 1 sin aumentaciones) | 2.184 | CC BY 4.0 |
| "weld data" (Roboflow) | 558 | CC BY 4.0 |
| **Total** | **2.742 → 2.699 radiografías distintas** | |

**Nombres unificados:** cada dataset nombraba los defectos distinto ("Lack Of Penetration" / "incomplete penetration", y hasta "Tungsten Inclusion" y "tungsten inclusion" como clases separadas). Un módulo con tests los lleva a 11 clases comunes en español.

![Defectos por tipo y recuadros por clase](capturas/etapa1-clases.png)

**Desbalance:** cinco defectos (porosidad, fisura, inclusión de escoria, falta de penetración y falta de fusión) concentran el 98% de los 7.856 recuadros. Las clases con menos de 100 ejemplos no alcanzan para entrenar bien; en la Etapa 2 se agrupan como "otro defecto".

**Separación:** 1.926 radiografías para entrenamiento, 408 para validación y 408 para prueba, sin fuga.

![Radiografías con defectos marcados](capturas/etapa1-radiografias-recuadros.png)

*Imágenes: datasets "weld" (kunkun) y "weld data" (Vayun Goel), Roboflow Universe, CC BY 4.0.*

**Etapa 1 terminada.**

---

## Etapa 2 · Modelo (17-nov-2026)

**Decisiones:**
- Detector **RT-DETR R18** (Apache 2.0) preentrenado, ajustado a soldaduras. No YOLO de Ultralytics: su licencia AGPL obligaría a publicar el código de la app.
- Radiografías: 5 defectos principales + **"otro defecto"**, que agrupa los seis tipos con menos de 100 ejemplos. El modelo igual avisa que hay algo y el inspector decide.
- El umbral de confianza se elige en **validación** para detectar al menos el 95% de las placas con defectos. La evaluación final se hace en **prueba**, con imágenes que el modelo nunca vio.
- Métricas: mAP@50 (estándar), recall y precisión por tipo de defecto, recall por placa (la que le importa al inspector) y galería de "dónde falla".
- Exportación a **ONNX** para que la app corra sin placa de video, verificada contra PyTorch con una radiografía real.

**Antes de gastar GPU:** el notebook completo se probó en la nube con un modelo chico y datos simulados (entrenamiento, evaluación, gráficos y exportación). Esa prueba encontró un detalle: con un modelo sin entrenar, todas las posiciones empatan en puntaje y ONNX y PyTorch desempatan distinto. Por eso la verificación final usa una imagen real y compara los hallazgos, no los números crudos.

### Primera corrida: radiografías (Kaggle, GPU T4, 2,1 h)

**Entrenamiento:** el mAP@50 en validación subió rápido (0,31 → 0,59 en 9 épocas) y llegó a su mejor valor, **0,626**, en la época 13. Después se estancó entre 0,60 y 0,62: con estos datos, el modelo ya aprendió lo principal. Se usa la época 13.

**Resultados en prueba (408 radiografías que el modelo nunca vio):**

| Métrica | Valor |
|---|---|
| mAP@50 | **0,607** (referencia publicada en SWRD: 0,66) |
| mAP@50-95 | 0,288 |
| Placas con defecto marcadas (recall por placa) | **90,4%** (369 de 408) |
| Umbral de confianza (elegido en validación) | 0,55 |

| Defecto | Recall | Precisión |
|---|---|---|
| Falta de penetración | 81% | 85% |
| Porosidad | 75% | 77% |
| Fisura | 69% | 84% |
| Inclusión de escoria | 64% | 78% |
| Falta de fusión | 45% | 62% |
| Otro defecto | 5% | 25% |

**Lectura honesta:**
- El umbral se eligió en validación para marcar el 95% de las placas con defectos, pero en prueba marcó el 90%. La calibración no se trasladó del todo: hace falta un margen de seguridad (elegir el umbral apuntando más alto en validación).
- "Otro defecto" casi no se detecta: tenía solo 120 ejemplos de entrenamiento repartidos en seis tipos distintos. Falta de fusión también es débil.
- **Limitación importante:** todas las radiografías del dataset tienen defectos, así que no se pudo medir cuántas falsas alarmas daría en placas sanas.
- La exportación a ONNX (81 MB) da exactamente los mismos hallazgos que PyTorch.

Las métricas quedan en `docs/metricas/radiografias.json` y un test del CI falla si un modelo nuevo rinde por debajo de un piso acordado.
