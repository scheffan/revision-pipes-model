# Licencias de los datos

| Dataset | Contenido | Licencia | Implicancias |
|---|---|---|---|
| RIAWELC | ~24.400 recortes de radiografías (224×224) en 4 clases | **A verificar** en la publicación original y su repositorio | Hasta confirmarla, no se redistribuye |
| SWRD | Más de 3.600 radiografías de soldaduras de costura con defectos marcados con polígonos | **No declarada.** La página oficial (tz-ndt.com, centro de descargas) solo ofrece el archivo `SWXD_Data.zip` por Google Drive o Baidu, sin términos de uso | Uso para investigación y portfolio citando el paper. No se redistribuye. Para un producto comercial hay que pedir permiso a los autores |
| Radiografías "weld" (Roboflow, kunkun) | 2.184 radiografías con 5 defectos: fisura, falta de fusión, falta de penetración, porosidad, inclusión de escoria. Se usa la versión 1, sin aumentaciones | CC BY 4.0 | Uso libre, incluso comercial, citando la fuente |
| Radiografías "weld data" (Roboflow, Vayun Goel) | 558 radiografías con 12 tipos de defecto | CC BY 4.0 | Uso libre, incluso comercial, citando la fuente |
| Fotos de cordones "Welding_Defects" (Roboflow) | 3.621 imágenes (con copias aumentadas): Good Weld, Bad Weld, Defect | CC BY 4.0 | Uso libre citando la fuente |
| Fotos de cordones "welding defects detection" (Roboflow) | 1.000 imágenes, mismas clases | Dominio público | Sin restricciones |
| GDXray (Welds) | Placas radiográficas completas, parte con recuadros anotados | Uso solo de investigación y educativo. Prohibidos la redistribución y el uso comercial. Hay que citar el paper | No se sube al repo ni a la demo. Sirve para evaluar, no para un producto comercial |

## Regla del proyecto
- El repo y la demo pública no incluyen imágenes de terceros.
- Un producto real para clientes se reentrena con radiografías propias del cliente, bajo su autorización.

## Pendiente
- [ ] Confirmar la licencia de RIAWELC.
- [x] SWRD revisado el 16-nov-2026: sin licencia publicada y el zip pesa 116 GB. Queda en pausa; se reemplaza por las radiografías de Roboflow con CC BY 4.0.
- [x] Fotos de cordones y radiografías de Roboflow: licencias confirmadas el 17-nov-2026.
- [ ] Revisar si conviene sumar WDXI o SWRD como fuentes extra.
