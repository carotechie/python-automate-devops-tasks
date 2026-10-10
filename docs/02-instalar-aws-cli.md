# 2 · Instalar AWS CLI v2

Necesitas la **versión 2**. La v1 no soporta bien IAM Identity Center: no entiende las
secciones `sso-session` de `~/.aws/config` ni el refresco automático del token, y
`aws sso login` se comporta distinto. Si ya tienes la v1 (instalada con `pip install awscli`),
desinstálala primero con `pip uninstall awscli`.

<details>
<summary><strong>Windows</strong></summary>

```powershell
msiexec.exe /i https://awscli.amazonaws.com/AWSCLIV2.msi
```

O con winget:

```powershell
winget install --id Amazon.AWSCLI -e
```

Cierra y vuelve a abrir la terminal.

</details>

<details>
<summary><strong>macOS</strong></summary>

Instalador oficial:

```bash
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /
```

O con Homebrew: `brew install awscli`.

</details>

<details>
<summary><strong>Linux (x86_64)</strong></summary>

```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

Para ARM (por ejemplo una Raspberry Pi o una instancia Graviton) cambia
`x86_64` por `aarch64` en la URL.

</details>

La documentación oficial está en
[docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).

## ¿Lo necesito para el laboratorio local?

No es obligatorio para el camino A (LocalStack + kind): los scripts usan `boto3`, no la CLI.
Sí lo necesitas para `aws sso login` (camino B) y para `aws eks update-kubeconfig`.

## Cómo verificar que funcionó

```bash
aws --version
```

Tienes que ver algo como `aws-cli/2.x.x Python/3.x.x ...`. Si empieza con `aws-cli/1.`,
tienes la v1: desinstálala y repite la instalación.
