# Reto 03 · Buckets S3 con acceso público

**Nivel:** Básico · **Tiempo estimado:** 1 h

## Contexto

Un bucket público por error es una de las fugas de datos más comunes. El *Block Public Access* es la primera defensa, pero puede estar desactivado a nivel bucket.

## Objetivo

Revisar todos los buckets y reportar los que no tienen el bloqueo de acceso público completo.

## Pistas

- Usa `s3.list_buckets` y, por cada bucket, `s3.get_public_access_block`.
- Si el bucket no tiene configuración, la API lanza un `ClientError` con código `NoSuchPublicAccessBlockConfiguration`: eso también es un hallazgo.
- Son 4 flags: `BlockPublicAcls`, `IgnorePublicAcls`, `BlockPublicPolicy`, `RestrictPublicBuckets`.
- Bonus del bonus: revisa también el bloqueo a nivel cuenta con `s3control.get_public_access_block`.

## Criterios de aceptación

- [ ] Lista todos los buckets de la cuenta
- [ ] Para cada uno muestra los 4 flags y un estado `OK` o `REVISAR`
- [ ] Trata la ausencia de configuración como `REVISAR`
- [ ] Maneja `AccessDenied` en un bucket sin cortar la ejecución
- [ ] Es de solo lectura
- [ ] Tiene tests con `moto` para un bucket protegido y uno sin configuración

---

Comparte tu solución abriendo un issue con la plantilla bonus-solucion o etiquetándome en redes.
