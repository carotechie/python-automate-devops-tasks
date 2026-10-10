# Reto 07 · Costos de los últimos 7 días por servicio

**Nivel:** Intermedio · **Tiempo estimado:** 1 h

## Contexto

Esperar a la factura de fin de mes para descubrir un gasto inesperado es tarde. Un resumen diario o semanal por servicio te avisa a tiempo.

## Objetivo

Mostrar el costo de los últimos 7 días agrupado por servicio, ordenado de mayor a menor.

## Pistas

- Usa `ce.get_cost_and_usage` con `Granularity='DAILY'` y `GroupBy` por `SERVICE`.
- Cost Explorer es global, pero el endpoint está en `us-east-1`.
- **Cada llamada a la API de Cost Explorer cuesta 0,01 USD.** Diseña el script para hacer una sola llamada.
- El rango `End` es exclusivo.
- Hay que activar Cost Explorer en la consola la primera vez (tarda hasta 24 h en tener datos).

## Criterios de aceptación

- [ ] Una sola llamada a la API por ejecución
- [ ] Tabla con servicio, costo total de los 7 días y promedio diario
- [ ] Muestra el total general y la moneda
- [ ] Oculta los servicios con costo menor a un umbral configurable
- [ ] Tiene tests con `botocore.stub.Stubber` (moto tiene soporte limitado de Cost Explorer)

---

Comparte tu solución abriendo un issue con la plantilla bonus-solucion o etiquetándome en redes.
