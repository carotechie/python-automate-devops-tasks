# 1 · Instalar Python 3.10 o superior

Los scripts usan sintaxis de Python 3.10 (por ejemplo `str | None` en las anotaciones),
así que necesitas **3.10, 3.11, 3.12 o más nuevo**.

## Paso 1: instala Python

<details>
<summary><strong>Windows</strong></summary>

Opción A, con `winget` (viene con Windows 10/11):

```powershell
winget install --id Python.Python.3.12 -e
```

Opción B, desde [python.org/downloads](https://www.python.org/downloads/): descarga el instalador
y **marca la casilla "Add python.exe to PATH"** antes de hacer clic en *Install Now*.

Cierra y vuelve a abrir la terminal para que tome el nuevo PATH.
En Windows el comando suele ser `py` o `python` (no `python3`).

</details>

<details>
<summary><strong>macOS</strong></summary>

Con [Homebrew](https://brew.sh):

```bash
brew install python@3.12
```

O descarga el instalador oficial de [python.org/downloads](https://www.python.org/downloads/macos/).
No uses el Python que trae el sistema (`/usr/bin/python3`): suele ser viejo.

</details>

<details>
<summary><strong>Linux (Debian / Ubuntu)</strong></summary>

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
python3 --version
```

Si tu distribución trae una versión menor a 3.10, en Ubuntu puedes usar el PPA *deadsnakes*:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install -y python3.12 python3.12-venv
```

En Fedora: `sudo dnf install python3`.

</details>

## Paso 2: crea un entorno virtual

Un entorno virtual (`.venv`) aísla las librerías de este repo de las del resto de tu sistema.
Desde la carpeta del repo:

```bash
python -m venv .venv
```

(En macOS y Linux puede que el comando sea `python3`. En Windows, `py -m venv .venv`).

## Paso 3: actívalo

Tienes que activarlo **cada vez que abras una terminal nueva**.

<details>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
.\.venv\Scripts\Activate.ps1
```

Si aparece un error de *execution policy*, ejecútalo una vez:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

En `cmd.exe` el comando es `.venv\Scripts\activate.bat`.

</details>

<details>
<summary><strong>macOS / Linux</strong></summary>

```bash
source .venv/bin/activate
```

</details>

Vas a ver `(.venv)` al inicio de la línea de la terminal.

## Paso 4: instala las dependencias

```bash
pip install -r requirements.txt
```

Si además quieres correr los tests y el linter:

```bash
pip install -r requirements-dev.txt
```

En macOS y Linux, `make setup` hace los pasos 2 y 4 por ti.

## Cómo verificar que funcionó

```bash
python --version
python -c "import boto3, kubernetes, pandas, tabulate; print('Dependencias OK')"
```

Tienes que ver `Python 3.10.x` o mayor y el mensaje `Dependencias OK`.

**Problemas comunes**

- `python: command not found`: prueba con `python3` (macOS/Linux) o `py` (Windows).
- `No module named boto3`: no activaste el entorno virtual. Repite el paso 3.
