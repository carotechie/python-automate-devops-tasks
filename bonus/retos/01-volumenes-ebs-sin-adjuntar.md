# Reto 01 · Volúmenes EBS sin adjuntar

**Nivel:** Básico · **Tiempo estimado:** 45 min

## Contexto

Cuando terminas una instancia, sus volúmenes EBS adicionales pueden quedar vivos (si `DeleteOnTermination` es `false`). Nadie los usa, pero se cobran cada mes.

## Objetivo

Listar los volúmenes en estado `available` (sin adjuntar) en varias regiones y estimar cuánto cuestan por mes.

## Pistas

- Usa `ec2.describe_volumes` con un filtro por `status`.
- Cada volumen tiene `Size` (GiB) y `VolumeType` (`gp3`, `gp2`, `io1`...).
- Para el costo, empieza con una tabla de precios por GiB/mes en un diccionario. Si quieres precisión, investiga la API `pricing` (solo está en `us-east-1` y `ap-south-1`).
- Reutiliza el patrón de regiones y paginadores de `02-buscar-recursos/find_ec2.py`.

## Criterios de aceptación

- [ ] Recorre al menos 3 regiones configurables con `--regions`
- [ ] Usa paginadores
- [ ] Muestra ID, región, tipo, tamaño, fecha de creación y costo estimado por mes
- [ ] Muestra el total estimado al final
- [ ] Soporta `--output json`
- [ ] Es de solo lectura: no borra nada
- [ ] Funciona contra LocalStack o moto (crea volúmenes sueltos para probar)

---

Comparte tu solución abriendo un issue con la plantilla bonus-solucion o etiquetándome en redes.
