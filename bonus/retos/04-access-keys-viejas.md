# Reto 04 · Access keys de IAM con más de 90 días

**Nivel:** Básico · **Tiempo estimado:** 45 min

## Contexto

Las access keys de larga duración son un riesgo: se filtran en repos, laptops y logs. La recomendación es rotarlas cada 90 días o, mejor, reemplazarlas por roles y SSO.

## Objetivo

Listar las access keys activas con más de 90 días de antigüedad y cuándo se usaron por última vez.

## Pistas

- Usa los paginadores de `iam.list_users` y `iam.list_access_keys`.
- `CreateDate` te da la antigüedad.
- `iam.get_access_key_last_used` te dice cuándo y en qué servicio se usó por última vez.
- Alternativa: `iam.generate_credential_report` + `get_credential_report` (CSV con todo en una llamada).

## Criterios de aceptación

- [ ] Configurable con `--max-age-days` (por defecto 90)
- [ ] Muestra usuario, ID de la key (solo los últimos 4 caracteres), estado, antigüedad y último uso
- [ ] Ignora las keys `Inactive` salvo que pases `--include-inactive`
- [ ] Es de solo lectura: no desactiva ni borra keys
- [ ] Tiene tests con `moto` (puedes manipular la fecha con `freezegun` o con un parámetro `now`)

---

Comparte tu solución abriendo un issue con la plantilla bonus-solucion o etiquetándome en redes.
