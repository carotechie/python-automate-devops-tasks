# Retos bonus

Ya corriste los 5 scripts. Ahora te toca a ti: cada reto plantea un problema real de DevOps
y te da pistas, pero no la solución.

## Reglas

- **Solo lectura.** Igual que los scripts del repo: ningún reto modifica ni borra recursos.
- **Practica sin gastar.** Usa LocalStack, moto o una cuenta de práctica con alerta de presupuesto.
- **Sin datos reales.** Nada de credenciales, IDs de cuenta ni nombres internos en tu solución.

## Retos por nivel

| # | Reto | Nivel | Tiempo |
|---|---|---|---|
| 01 | [Volúmenes EBS sin adjuntar](retos/01-volumenes-ebs-sin-adjuntar.md) | Básico | 45 min |
| 02 | [Elastic IPs sin usar](retos/02-elastic-ips-sin-usar.md) | Básico | 30 min |
| 03 | [Buckets S3 con acceso público](retos/03-buckets-s3-publicos.md) | Básico | 1 h |
| 04 | [Access keys de IAM con más de 90 días](retos/04-access-keys-viejas.md) | Básico | 45 min |
| 05 | [Enviar el resumen del incidente a Slack o Teams](retos/05-incidente-a-slack-o-teams.md) | Intermedio | 1 h |
| 06 | [Validar tags obligatorios](retos/06-validar-tags-obligatorios.md) | Intermedio | 1 h 30 min |
| 07 | [Costos de los últimos 7 días por servicio](retos/07-costos-ultimos-7-dias.md) | Intermedio | 1 h |
| 08 | [pods_check.py como CronJob de Kubernetes](retos/08-pods-check-cronjob.md) | Intermedio | 2 h |
| 09 | [Una CLI única con typer y rich](retos/09-cli-unica-con-typer.md) | Avanzado | 4 h |
| 10 | [Alerta de credenciales a punto de vencer](retos/10-alerta-credenciales-por-vencer.md) | Avanzado | 2 h |
| 11 | [Publicar el reporte semanal en GitHub Pages](retos/11-reporte-en-github-pages.md) | Avanzado | 2 h |
| 12 | [Tests con moto y badge de cobertura](retos/12-tests-con-moto-y-cobertura.md) | Avanzado | 2 h |

## Cómo encarar un reto

1. Lee el contexto y pregúntate si cumple la regla de 3 de 4 (ver el README principal).
2. Busca en los scripts del repo un patrón parecido: regiones, paginadores, `main(argv=None)`, tests.
3. Escribe primero el test con `moto` o `Stubber`, después el código.
4. Revisa la checklist de criterios de aceptación.

## Comparte tu solución

Abre un issue con la plantilla **bonus-solucion** o etiquétame en redes. Me encanta ver qué
automatizaciones arman.
