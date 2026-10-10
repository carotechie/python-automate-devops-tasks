# 03 · Pods con fallas

**El problema:** `kubectl get pods -A` en un cluster con cientos de pods, buscando a ojo cuál
dice `CrashLoopBackOff`.

**La automatización:** `pods_check.py` lista solo los pods con problemas y devuelve exit code 1
si encuentra alguno, para que puedas usarlo en CI, en un cron o como check de un pipeline.

## Qué detecta

| Situación | Cómo la detecta | Se reporta como |
|---|---|---|
| Contenedor que se reinicia sin parar | `state.waiting.reason` | `CrashLoopBackOff` |
| Imagen que no existe o sin permisos | `state.waiting.reason` | `ImagePullBackOff`, `ErrImagePull` |
| Secret o ConfigMap faltante | `state.waiting.reason` | `CreateContainerConfigError` |
| Pod que no entra en ningún nodo | `phase == Pending` + condición `PodScheduled` | `Unschedulable` |
| Pod que está arrancando | `ContainerCreating`, `PodInitializing` | **Se ignora** |

También revisa los *init containers*. Los pods `Succeeded` (jobs terminados) no se reportan.

## Uso

```bash
# Todo el cluster
python 03-pods-con-fallas/pods_check.py --context kind-pyladies-lab

# Un namespace
python 03-pods-con-fallas/pods_check.py --context kind-pyladies-lab -n lab

# JSON, para procesarlo en otro paso
python 03-pods-con-fallas/pods_check.py --context kind-pyladies-lab --output json
```

Usa la librería oficial `kubernetes` con `load_kube_config()`, así que respeta `KUBECONFIG`,
`--kubeconfig` y `--context`. Si corre dentro del cluster (por ejemplo como CronJob), usa la
configuración in-cluster automáticamente.

### Exit codes

| Código | Significado |
|---|---|
| `0` | No hay pods con problemas |
| `1` | Hay al menos un pod con problemas |
| `2` | No se pudo consultar el cluster (kubeconfig, permisos, conexión) |

Ejemplo en un pipeline o cron:

```bash
python 03-pods-con-fallas/pods_check.py -n lab || echo "Hay pods con fallas, revisa el reporte"
```

## Contra el laboratorio local

```bash
make lab-up
source lab/lab.env   # define KUBE_CONTEXT=kind-pyladies-lab
python 03-pods-con-fallas/pods_check.py
```

Salida de ejemplo (los sufijos de los pods cambian en cada cluster; `make demo` te muestra la tuya):

```text
| Namespace   | Pod                          | Contenedor   | Razón            |   Reinicios |
|-------------|------------------------------|--------------|------------------|-------------|
| lab         | broken-image-7b9c8d5f4-mz2lq | app          | ImagePullBackOff |           0 |
| lab         | checkout-59d8f7c6b4-7lx2c    | checkout     | CrashLoopBackOff |           4 |
| lab         | checkout-59d8f7c6b4-v8n4k    | checkout     | CrashLoopBackOff |           4 |
| lab         | crashloop-5f6b7c8d9-hk3jd    | app          | CrashLoopBackOff |           5 |
| lab         | too-big-84c7d9f6b-wq9rt      | -            | Unschedulable    |           0 |

5 de 17 pods con problemas
```

Justo después de `make lab-up` puedes ver `ErrImagePull` en lugar de `ImagePullBackOff`, o
`Error` antes de `CrashLoopBackOff`: espera 1 o 2 minutos.

## Permisos mínimos (RBAC)

Necesita `list` sobre `pods`. Para todo el cluster, un `ClusterRole`:

```yaml
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["list"]
```

Convertirlo en un CronJob es el [reto bonus 08](../bonus/retos/08-pods-check-cronjob.md).
