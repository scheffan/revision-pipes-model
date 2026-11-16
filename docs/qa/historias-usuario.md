# Historias de usuario

Roles:
- **Técnico de obra:** saca y sube las radiografías.
- **Inspector:** certificado (Nivel II/III), revisa y aprueba a distancia.
- **Administrador:** configura el proyecto y la norma.

---

## HU-01 · Subir un lote de radiografías
**Como** técnico de obra **quiero** subir las radiografías de un día con el número de cada soldadura **para** que el inspector las revise sin viajar.

Criterios de aceptación:
- Dado un lote con imágenes válidas, cuando lo subo, cada imagen queda asociada a su número de soldadura.
- Dada una imagen dañada o demasiado chica, cuando la subo, veo un mensaje claro y el resto del lote se carga igual.
- No se aceptan dos imágenes con el mismo número de soldadura en el mismo lote sin confirmación.

## HU-02 · Ver las placas ordenadas por prioridad
**Como** inspector **quiero** ver primero las placas con más probabilidad de defecto **para** dedicar mi tiempo a lo dudoso.

Criterios de aceptación:
- El lote se muestra ordenado de mayor a menor riesgo según el modelo.
- Cada placa muestra las zonas marcadas y la clase sugerida con su confianza.
- Se puede filtrar por "sin revisar", "dudosas" y "revisadas".

## HU-03 · Corregir lo que marcó la IA
**Como** inspector **quiero** aceptar, corregir o descartar cada indicación **para** que el informe refleje mi criterio y no el del modelo.

Criterios de aceptación:
- Cada indicación tiene tres acciones: aceptar, cambiar clase, descartar.
- Puedo marcar una zona que la IA no detectó.
- Mis cambios quedan guardados aunque cierre la app.

## HU-04 · Aprobar o rechazar una soldadura
**Como** inspector **quiero** decidir el estado de cada soldadura **para** cerrar la inspección.

Criterios de aceptación:
- Estados posibles: aprobada, rechazada (a reparar), a revisar en obra.
- No se puede aprobar una soldadura con indicaciones sin revisar.
- La decisión siempre es del inspector: la IA nunca cambia un estado.

## HU-05 · Generar el informe
**Como** inspector **quiero** un informe PDF del lote **para** entregarlo a la inspección de obra.

Criterios de aceptación:
- Incluye proyecto, lote, fecha, inspector, norma configurada y estado de cada soldadura.
- Indica qué indicaciones vinieron de la IA y cuáles agregó o corrigió el inspector.

## HU-06 · Registro de auditoría
**Como** administrador **quiero** ver quién decidió qué y cuándo **para** tener trazabilidad ante un reclamo.

Criterios de aceptación:
- Toda acción (subida, corrección, decisión, informe) queda registrada con usuario y hora.
- Un registro no se puede borrar ni editar; una corrección genera un registro nuevo.

## HU-07 · Configurar la norma
**Como** administrador **quiero** elegir el criterio de aceptación del proyecto (API 1104, ISO 5817) **para** usar la herramienta en distintos países.

Criterios de aceptación:
- La norma elegida aparece en el informe.
- El MVP usa una tabla simplificada de tipos de defecto; la evaluación con medidas la hace el inspector.
