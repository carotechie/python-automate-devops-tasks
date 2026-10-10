# Variables para usar los scripts contra el laboratorio local en PowerShell.
# Uso: . .\lab\lab.env.ps1
$env:AWS_ENDPOINT_URL = "http://localhost:4566"
$env:AWS_ACCESS_KEY_ID = "test"
$env:AWS_SECRET_ACCESS_KEY = "test"
$env:AWS_DEFAULT_REGION = "us-east-1"
$env:AWS_REGION = "us-east-1"
# Fija los scripts de Kubernetes al cluster del laboratorio, aunque tengas otros contextos.
$env:KUBE_CONTEXT = "kind-pyladies-lab"
