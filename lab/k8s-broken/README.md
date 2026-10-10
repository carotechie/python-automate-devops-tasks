# Manifests que fallan a propósito

| Archivo | Deployment | Qué pasa | Lo detecta |
|---|---|---|---|
| `01-web-healthy.yaml` | `web` | Funciona bien (2 réplicas) | Nada que reportar |
| `02-image-pull-backoff.yaml` | `broken-image` | La imagen no existe | `ImagePullBackOff` / `ErrImagePull` |
| `03-crashloop.yaml` | `crashloop` | El comando sale con código 1 | `CrashLoopBackOff` |
| `04-pending.yaml` | `too-big` | Pide 100 CPU | `Pending` (`Unschedulable`) |
| `05-checkout.yaml` + `incident/checkout-v2.4.1.yaml` | `checkout` | v2.4.0 funciona; v2.4.1 no encuentra su base de datos y el rollout se traba | 1 de 3 listas, 2 en `CrashLoopBackOff` + logs para el triage |

`make lab-up` aplica la carpeta, espera a que `checkout` v2.4.0 esté lista y después aplica
`incident/`, para simular un deploy que rompe producción. A mano:

```bash
kubectl --context kind-pyladies-lab apply -f lab/k8s-broken/
kubectl --context kind-pyladies-lab -n lab rollout status deployment/checkout --timeout=180s
kubectl --context kind-pyladies-lab apply -f lab/k8s-broken/incident/
```

`kubectl -n lab rollout history deployment/checkout` muestra los dos cambios, y
`kubectl -n lab rollout undo deployment/checkout` vuelve a v2.4.0 (eso sí lo haces tú: los scripts no modifican nada).
Los pods con `CrashLoopBackOff` tardan 1 o 2 minutos en llegar a ese estado.
