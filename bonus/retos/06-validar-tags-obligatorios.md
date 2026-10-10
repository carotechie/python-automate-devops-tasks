# Reto 06 · Validar tags obligatorios

**Nivel:** Intermedio · **Tiempo estimado:** 1 h 30 min

## Contexto

Sin tags no sabes de quién es un recurso, en qué ambiente está ni a qué centro de costos cargarlo. Los tags obligatorios son la base del FinOps.

## Objetivo

Generar un reporte de los recursos que no tienen los tags `owner`, `env` y `cost-center`.

## Pistas

- Para empezar, revisa instancias EC2, volúmenes EBS y buckets S3.
- Para revisar muchos tipos de recursos de una vez, investiga `resourcegroupstaggingapi.get_resources` (tiene paginador).
- Ojo: la Tagging API no devuelve recursos que **nunca** tuvieron tags. Piensa cómo cubrir ese caso.
- Para el reporte, `pandas` ya está en `requirements.txt`.

## Criterios de aceptación

- [ ] La lista de tags obligatorios es configurable (`--required owner,env,cost-center`)
- [ ] Muestra el ARN o ID del recurso, su tipo y qué tags le faltan
- [ ] Genera Markdown o CSV
- [ ] Muestra un porcentaje de cumplimiento
- [ ] Es de solo lectura: no agrega tags
- [ ] Tiene tests con `moto`

---

Comparte tu solución abriendo un issue con la plantilla bonus-solucion o etiquetándome en redes.
