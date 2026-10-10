# 04 · Triage de incidentes

**El problema:** suena la alerta. Los primeros 10 minutos son siempre los mismos comandos:
`get deployment`, `get pods`, `describe pod`, `get events`, `logs --previous`... y copiar todo
en el canal del incidente.

**La automatización:** `triage.py` junta esa información en un archivo Markdown listo para
pegar en el ticket o en el canal.

> **El script no arregla nada.** Es de solo lectura. Te ahorra los primeros minutos de
> investigación para que llegues a la causa más rápido, con los datos ya ordenados.

## Qué junta

| Sección | De dónde sale |
|---|---|
| Deployment | Réplicas listas vs. deseadas, imagen, versión (label `app.kubernetes.io/version`), revisión con su `change-cause` y fecha del último rollout (la del ReplicaSet de la revisión actual) |
| Pods que no están listos | Pods del selector del deployment cuya condición `Ready` no es `True` |
| Últimos eventos Warning | Eventos `type=Warning` del deployment, sus ReplicaSets y sus pods, del más reciente al más viejo |
| Logs | Últimas 20 líneas del log **anterior** (`previous=True`) del primer pod caído. Si no hay log anterior, usa el actual y lo aclara |

## Uso

```bash
python 04-triage-incidentes/triage.py --namespace lab --app checkout   # con source lab/lab.env
```

Opciones útiles: `--tail 50` (más líneas de log), `--events 20`, `--output-dir incidents/`.

Genera `incident-summary-checkout-20261010-154901.md` en la carpeta actual y lo imprime.
Estos archivos están en `.gitignore` porque pueden tener datos internos.

## Ejemplo de salida

Salida de ejemplo con la app `checkout` del laboratorio (`make demo` te muestra la tuya). El laboratorio
simula un deploy de v2.4.1 que rompe la conexión a la base y deja el rollout trabado:

````markdown
# Resumen de incidente: checkout

- **Namespace:** `lab`
- **Generado:** 2026-10-10 15:49:01 UTC
- **Estado:** DEGRADADO (1/3 réplicas listas)

> Este resumen no arregla nada: junta los datos para que empieces a investigar.

## Deployment

| Campo | Valor |
|---|---|
| Réplicas listas / deseadas | 1 / 3 |
| Actualizadas / disponibles | 2 / 1 |
| Imagen | `busybox:1.36` |
| Versión | v2.4.1 |
| Revisión | 2 · v2.4.1: mueve el carrito a postgres |
| Último rollout | 2026-10-10 15:37:01 UTC (hace 12 min) |

## Pods que no están listos

| Pod | Fase | Razón | Reinicios | Nodo |
|---|---|---|---|---|
| checkout-59d8f7c6b4-7lx2c | Running | CrashLoopBackOff | 4 | pyladies-lab-control-plane |
| checkout-59d8f7c6b4-v8n4k | Running | CrashLoopBackOff | 4 | pyladies-lab-control-plane |

## Últimos eventos Warning

| Hora | Objeto | Razón | Veces | Mensaje |
|---|---|---|---|---|
| 2026-10-10 15:48:40 UTC | Pod/checkout-59d8f7c6b4-7lx2c | BackOff | 14 | Back-off restarting failed container checkout in pod checkout-59d8f7c6b4-7lx2c_lab |
| 2026-10-10 15:48:12 UTC | Pod/checkout-59d8f7c6b4-v8n4k | BackOff | 13 | Back-off restarting failed container checkout in pod checkout-59d8f7c6b4-v8n4k_lab |

## Logs

Últimas 20 líneas del log anterior (`previous=True`) de `checkout-59d8f7c6b4-7lx2c`:

```text
checkout v2.4.1 starting
connecting to postgres at db:5432
attempt 1/3: could not connect to db:5432
attempt 2/3: could not connect to db:5432
attempt 3/3: could not connect to db:5432
ConnectionError: could not connect to db:5432
```

## Próximos pasos sugeridos

- `kubectl -n lab describe deployment checkout`
- `kubectl -n lab rollout history deployment/checkout`
- `kubectl -n lab describe pod checkout-59d8f7c6b4-7lx2c`
````

Con esto ya sabes en 10 segundos que el problema empezó con el cambio a v2.4.1 (hace 12 min),
que queda 1 réplica sana de la versión anterior y que la causa es la conexión a la base, no la imagen
ni los recursos. El siguiente paso lo decides tú, por ejemplo `kubectl -n lab rollout undo deployment/checkout`.

## Permisos mínimos (RBAC)

`get` sobre `deployments`, `list` sobre `replicasets`, `pods` y `events`, y `get` sobre `pods/log`.

Enviar este resumen a Slack o Teams es el [reto bonus 05](../bonus/retos/05-incidente-a-slack-o-teams.md).
