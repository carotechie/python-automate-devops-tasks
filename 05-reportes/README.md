# 05 · Reportes semanales

**El problema:** todos los lunes alguien pregunta "¿cuántas instancias tenemos en staging?"
y alguien arma una planilla a mano.

**La automatización:** `weekly_report.py` cuenta instancias EC2 y pods por ambiente y genera
el reporte en Markdown, CSV o JSON. Con un workflow programado, el reporte aparece solo.

## Cómo identifica cada ambiente

| Modo | EC2 | Pods |
|---|---|---|
| Por defecto | Instancias con el tag `env=<ambiente>` | Pods con la label `env=<ambiente>` en todo el cluster |
| `--profile-per-env` | Todas las instancias de la cuenta del perfil AWS que se llama como el ambiente | — |
| `--context-per-env` | — | Todos los pods del contexto de kubeconfig que se llama como el ambiente |

Combinando `--profile-per-env` y `--context-per-env` tienes el modelo de la diapositiva:
una sesión de AWS y un cluster por ambiente.

Las instancias `terminated` no se cuentan. `--tag-key` cambia el nombre del tag (por defecto `env`).

## Uso

```bash
# Markdown por pantalla
python 05-reportes/weekly_report.py --env staging --env dev --context kind-pyladies-lab

# CSV a un archivo
python 05-reportes/weekly_report.py --env staging --env dev --format csv --output-file reports/weekly.csv

# Un perfil de AWS por ambiente (por ejemplo los que crea hub_switch.py)
python 05-reportes/weekly_report.py --env staging-readonly --env prod-readonly --profile-per-env --skip-k8s

# Como en la charla: un perfil de AWS y un contexto de kubeconfig por ambiente
python 05-reportes/weekly_report.py --env dev --env staging --env prod --profile-per-env --context-per-env

# Sin Kubernetes
python 05-reportes/weekly_report.py --env staging --env dev --skip-k8s --format json
```

## Contra el laboratorio local

```bash
make lab-up
source lab/lab.env
python 05-reportes/weekly_report.py --env dev --env staging --context kind-pyladies-lab
```

Salida real de la parte de EC2 contra un emulador local (`--skip-k8s`):

```text
# Reporte semanal de infraestructura

- **Generado:** 2026-10-10 15:48 UTC
- **Regiones:** us-east-1, eu-west-1, sa-east-1

| Ambiente   |   EC2 total |   EC2 en ejecución |
|:-----------|------------:|-------------------:|
| dev        |           0 |                  0 |
| staging    |           3 |                  2 |
| TOTAL      |           3 |                  2 |
```

Con Kubernetes se agregan las columnas `Pods` y `Pods sin Running`.

## Workflow programado

[`.github/workflows/weekly-report.yml`](../.github/workflows/weekly-report.yml) corre los
lunes a las 09:00 UTC (y a mano con *Run workflow*):

1. Levanta LocalStack como *service container*.
2. Carga los datos de ejemplo con `lab/seed_localstack.py`.
3. Genera el reporte, lo muestra en el *Job summary* y lo sube como artefacto.

Corre contra LocalStack para que cualquiera pueda reproducirlo sin una cuenta. Para usarlo con
AWS real, reemplaza LocalStack por
[`aws-actions/configure-aws-credentials`](https://github.com/aws-actions/configure-aws-credentials)
con OIDC (sin access keys guardadas en secretos) y quita `AWS_ENDPOINT_URL`.

Publicarlo en GitHub Pages es el [reto bonus 11](../bonus/retos/11-reporte-en-github-pages.md).
