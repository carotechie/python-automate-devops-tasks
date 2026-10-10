# Reto 02 · Elastic IPs sin usar

**Nivel:** Básico · **Tiempo estimado:** 30 min

## Contexto

Desde 2024 AWS cobra todas las direcciones IPv4 públicas por hora. Una Elastic IP reservada que no está asociada a nada es dinero que se va sin motivo.

## Objetivo

Listar las Elastic IPs que no están asociadas a ninguna instancia ni interfaz de red.

## Pistas

- Usa `ec2.describe_addresses`.
- Una EIP sin usar no tiene `AssociationId`.
- Esta API no tiene paginador: revisa por qué y si necesitas uno.
- Mira los tags de cada EIP: a veces dicen quién la reservó.

## Criterios de aceptación

- [ ] Revisa varias regiones
- [ ] Muestra IP pública, `AllocationId`, región y tags
- [ ] Indica cuántas hay y el costo estimado por mes (usa el precio por hora de IPv4 pública vigente)
- [ ] Exit code 1 si encuentra alguna, para usarlo en CI
- [ ] Es de solo lectura: no libera ninguna IP
- [ ] Tiene al menos un test con `moto`

---

Comparte tu solución abriendo un issue con la plantilla bonus-solucion o etiquetándome en redes.
