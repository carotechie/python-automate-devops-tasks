# Reto 12 · Tests con moto y badge de cobertura

**Nivel:** Avanzado · **Tiempo estimado:** 2 h

## Contexto

Un script sin tests es un script que da miedo tocar. Con `moto` puedes probar código de AWS sin cuenta y sin costo.

## Objetivo

Escribir tests con `moto` para uno de tus retos y agregar un badge de cobertura al README.

## Pistas

- Usa `@mock_aws` o el context manager `with mock_aws():`.
- Crea los recursos de prueba en el test (o en un fixture) antes de llamar a tu función.
- Mide la cobertura con `pytest-cov` (`pytest --cov`).
- Para el badge: un servicio como Codecov, o genera el badge en el propio workflow y publícalo con el reto 11.

## Criterios de aceptación

- [ ] Al menos 5 tests para un reto propio, con casos felices y de error
- [ ] La cobertura de ese script es de 80 % o más
- [ ] El CI corre la cobertura en cada PR
- [ ] El README muestra un badge de cobertura que se actualiza solo
- [ ] Ningún test necesita credenciales reales

---

Comparte tu solución abriendo un issue con la plantilla bonus-solucion o etiquetándome en redes.
