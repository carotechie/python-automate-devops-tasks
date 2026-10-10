# Reto 08 · pods_check.py como CronJob de Kubernetes

**Nivel:** Intermedio · **Tiempo estimado:** 2 h

## Contexto

Correr `pods_check.py` a mano sirve, pero lo ideal es que el cluster se revise solo cada pocos minutos.

## Objetivo

Empaquetar `pods_check.py` en una imagen y correrlo como CronJob en el cluster de kind, publicando el resultado.

## Pistas

- Escribe un `Dockerfile` chico (`python:3.12-slim`) que copie solo el script y sus dependencias.
- Carga la imagen en kind con `kind load docker-image`.
- El script ya soporta configuración in-cluster: necesita un `ServiceAccount` con un `ClusterRole` que permita `list` sobre `pods`.
- Para "publicar": puede ser un ConfigMap con el último resultado, un log estructurado en JSON o el webhook del reto 05.
- Revisa `concurrencyPolicy` y `successfulJobsHistoryLimit`.

## Criterios de aceptación

- [ ] `Dockerfile` y manifests en una carpeta nueva
- [ ] El CronJob corre cada 5 minutos en kind
- [ ] Usa un ServiceAccount con permisos mínimos (no `cluster-admin`)
- [ ] El resultado queda visible fuera del log del pod
- [ ] El Job falla (exit 1) cuando hay pods con problemas
- [ ] README con los comandos para desplegarlo y borrarlo

---

Comparte tu solución abriendo un issue con la plantilla bonus-solucion o etiquetándome en redes.
