# 6 · Kubernetes local con kind (o minikube)

Para los scripts 03 y 04 necesitas un cluster. **No uses EKS para practicar**: cobra por hora
desde que lo creas. Con kind tienes un cluster real dentro de Docker, gratis.

Necesitas tres cosas: **Docker**, **kubectl** y **kind** (o minikube).

## Paso 1: instala Docker

<details>
<summary><strong>Windows</strong></summary>

Instala [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) con el
backend WSL 2. Ábrelo y espera a que diga *Engine running*.

</details>

<details>
<summary><strong>macOS</strong></summary>

Instala [Docker Desktop](https://docs.docker.com/desktop/setup/install/mac-install/), o una
alternativa liviana como [Colima](https://github.com/abiosoft/colima):

```bash
brew install colima docker
colima start --cpu 2 --memory 4
```

</details>

<details>
<summary><strong>Linux</strong></summary>

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
newgrp docker
```

</details>

## Paso 2: instala kubectl

<details>
<summary><strong>Windows</strong></summary>

```powershell
winget install --id Kubernetes.kubectl -e
```

</details>

<details>
<summary><strong>macOS</strong></summary>

```bash
brew install kubectl
```

</details>

<details>
<summary><strong>Linux</strong></summary>

```bash
curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -m 0755 kubectl /usr/local/bin/kubectl
```

</details>

## Paso 3: instala kind

<details>
<summary><strong>Windows</strong></summary>

```powershell
winget install --id Kubernetes.kind -e
```

</details>

<details>
<summary><strong>macOS</strong></summary>

```bash
brew install kind
```

</details>

<details>
<summary><strong>Linux</strong></summary>

```bash
curl -Lo ./kind https://kind.sigs.k8s.io/dl/latest/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
```

</details>

## Paso 4: crea el cluster del laboratorio

Desde la raíz del repo:

```bash
kind create cluster --config lab/kind-config.yaml
```

Esto crea el cluster `pyladies-lab` y el contexto `kind-pyladies-lab` en tu kubeconfig.

Después carga las apps que fallan a propósito y simula el deploy roto de `checkout`:

```bash
kubectl --context kind-pyladies-lab apply -f lab/k8s-broken/
kubectl --context kind-pyladies-lab -n lab rollout status deployment/checkout --timeout=180s
kubectl --context kind-pyladies-lab apply -f lab/k8s-broken/incident/
```

`make lab-up` hace todos estos pasos (y además levanta LocalStack).

> **Importante:** si en tu kubeconfig también tienes clusters reales, pasa siempre
> `--context kind-pyladies-lab` a `kubectl`. Los scripts usan la variable `KUBE_CONTEXT`,
> que `source lab/lab.env` deja apuntando a `kind-pyladies-lab`. Así nunca apuntas a otro
> cluster por accidente.

## Alternativa: minikube

```bash
minikube start -p pyladies-lab --cpus 2 --memory 4096
kubectl --context pyladies-lab apply -f lab/k8s-broken/
kubectl --context pyladies-lab -n lab rollout status deployment/checkout --timeout=180s
kubectl --context pyladies-lab apply -f lab/k8s-broken/incident/
```

En los scripts usa `--context pyladies-lab` o `export KUBE_CONTEXT=pyladies-lab`.

## Cómo verificar que funcionó

```bash
kubectl --context kind-pyladies-lab get nodes
```

Tienes que ver un nodo `pyladies-lab-control-plane` en estado `Ready`. Después:

```bash
kubectl --context kind-pyladies-lab -n lab get pods
```

Vas a ver los pods de `web` en `Running`, 1 pod de `checkout` sano (v2.4.0), 2 pods de
`checkout` fallando (v2.4.1) y los demás deployments rotos. Los `CrashLoopBackOff` tardan
1 o 2 minutos en aparecer.

## Usar tu propio cluster (EKS u otro)

Si ya tienes un cluster, los scripts 03, 04 y 05 funcionan igual: usan el kubeconfig, así que
les da lo mismo si el cluster es kind, EKS, GKE, AKS o k3s. Son de solo lectura.

> **No crees un cluster EKS solo para practicar.** El plano de control de EKS cobra por hora
> desde que el cluster existe (alrededor de 0,10 USD por hora, unos 73 USD al mes), más los
> nodos. Si no tienes uno, usa kind.

### Paso 1: reemplaza las variables con los datos de tu cluster

Copia `.env.example` como `.env` y edita:

```bash
EKS_CLUSTER_NAME=eks-dev   # reemplaza por el nombre de tu cluster
KUBE_CONTEXT=eks-dev       # el contexto que usarán los scripts (puede ser igual al cluster)
AWS_REGION=us-east-1       # la región de tu cluster
```

Para ver los clusters de tu cuenta:

```bash
aws eks list-clusters --region us-east-1 --profile <tu-perfil>
```

### Paso 2: crea el contexto en tu kubeconfig

<details>
<summary><strong>Con SSO (recomendado)</strong></summary>

`sso_switch.py` obtiene las credenciales y, como `EKS_CLUSTER_NAME` está definida, ejecuta
`aws eks update-kubeconfig` por ti. El contexto queda con el nombre del cluster:

```bash
set -a && source .env && set +a
python 01-acceso-multicuenta/sso_switch.py --profile-name caro
```

</details>

<details>
<summary><strong>Con un perfil que ya tienes</strong></summary>

```bash
set -a && source .env && set +a
aws eks update-kubeconfig --name "$EKS_CLUSTER_NAME" --region "$AWS_REGION" --alias "$KUBE_CONTEXT" --profile <tu-perfil>
```

</details>

<details>
<summary><strong>Otro proveedor (GKE, AKS, k3s)</strong></summary>

Usa el comando de tu proveedor para agregar el cluster al kubeconfig y después:

```bash
kubectl config get-contexts
export KUBE_CONTEXT=<nombre-del-contexto>
```

</details>

### Paso 3: corre los scripts con tus datos

```bash
python 03-pods-con-fallas/pods_check.py --namespace <tu-namespace>
python 04-triage-incidentes/triage.py --namespace <tu-namespace> --app <tu-deployment>
python 05-reportes/weekly_report.py --env <tu-ambiente>
```

Para `triage.py`, `--app` es el nombre del **deployment**. Si tus pods no tienen la label
`app.kubernetes.io/version`, la fila *Versión* muestra `-` y el resto del resumen funciona igual.
`weekly_report.py` cuenta los pods con la label `env=<ambiente>`; si usas otra label, pásala con `--tag-key`.

### Permisos que necesitas

Con tu usuario de EKS (Access Entries o `aws-auth`) o en cualquier cluster, alcanza con un rol de
solo lectura como este:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: python-automatiza-devops-readonly
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log", "events"]
    verbs: ["get", "list"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets"]
    verbs: ["get", "list"]
```

En EKS, la política de acceso administrada `AmazonEKSViewPolicy` cubre todo esto salvo `pods/log`:
si necesitas los logs para `triage.py`, agrega este `ClusterRole` y asígnaselo a tu usuario o grupo.

### Cómo verificar que funcionó

```bash
kubectl --context "$KUBE_CONTEXT" get nodes
python 03-pods-con-fallas/pods_check.py
```

## Para borrar todo

```bash
kind delete cluster --name pyladies-lab
```
