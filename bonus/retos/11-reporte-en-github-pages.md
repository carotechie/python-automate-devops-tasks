# Reto 11 · Publicar el reporte semanal en GitHub Pages

**Nivel:** Avanzado · **Tiempo estimado:** 2 h

## Contexto

El workflow `weekly-report.yml` deja el reporte como artefacto, pero nadie va a descargar un zip todos los lunes. Una página web con el historial es mucho más útil.

## Objetivo

Publicar el reporte semanal como página en GitHub Pages desde el workflow, manteniendo el historial.

## Pistas

- Mira las actions oficiales `actions/upload-pages-artifact` y `actions/deploy-pages`.
- El job necesita los permisos `pages: write` e `id-token: write`.
- Puedes convertir el Markdown a HTML con la librería `markdown`, o generar el HTML directo con `DataFrame.to_html()`.
- Para el historial: guarda cada reporte con fecha y genera un `index.html` que los liste.

## Criterios de aceptación

- [ ] El workflow publica una página con el último reporte
- [ ] Hay un índice con los reportes anteriores
- [ ] La página no expone IDs de cuenta ni datos sensibles
- [ ] El workflow sigue funcionando con LocalStack
- [ ] README con cómo activar Pages en el repo

---

Comparte tu solución abriendo un issue con la plantilla bonus-solucion o etiquetándome en redes.
