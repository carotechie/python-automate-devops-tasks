#!/usr/bin/env python3
"""Cambia de cuenta y rol usando IAM Identity Center (SSO).

Reutiliza el token que deja `aws sso login` en ~/.aws/sso/cache, lista las
cuentas y roles a los que tienes acceso, pide credenciales temporales y las
guarda como un perfil en ~/.aws/credentials.

Es de solo lectura sobre AWS: no crea ni modifica recursos.
"""

from __future__ import annotations

import argparse
import configparser
import json
import logging
import os
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

log = logging.getLogger("sso_switch")

DEFAULT_CACHE_DIR = Path.home() / ".aws" / "sso" / "cache"


class SwitchError(Exception):
    """Error esperado que se muestra a la persona sin traceback."""


# --- Token de SSO -----------------------------------------------------------


def parse_expiration(value: str) -> datetime:
    """Convierte la fecha de expiración del caché de SSO a datetime con zona."""
    normalized = value.strip().replace("UTC", "+00:00").replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def cached_token(start_url: str, cache_dir: Path, now: datetime | None = None) -> dict:
    """Busca en el caché de SSO el token vigente para la start URL indicada."""
    now = now or datetime.now(timezone.utc)
    wanted = start_url.rstrip("/")
    best: dict | None = None

    if not cache_dir.is_dir():
        raise SwitchError(f"No existe el caché de SSO en {cache_dir}. Ejecuta primero: aws sso login")

    for path in cache_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            log.debug("skipping unreadable cache file %s", path)
            continue
        if "accessToken" not in data or "expiresAt" not in data:
            continue
        if data.get("startUrl", "").rstrip("/") != wanted:
            continue
        expires_at = parse_expiration(data["expiresAt"])
        if expires_at <= now:
            continue
        if best is None or expires_at > best["expires_at"]:
            best = {"access_token": data["accessToken"], "expires_at": expires_at}

    if best is None:
        raise SwitchError(
            f"No hay un token de SSO vigente para {start_url}. Ejecuta: aws sso login --profile <tu-perfil-sso>"
        )
    return best


# --- API de SSO -------------------------------------------------------------


def build_sso_client(region: str):
    return boto3.client("sso", region_name=region)


def list_accounts(sso_client, access_token: str) -> list[dict]:
    """Devuelve las cuentas disponibles ordenadas por nombre."""
    paginator = sso_client.get_paginator("list_accounts")
    accounts = []
    for page in paginator.paginate(accessToken=access_token):
        for account in page.get("accountList", []):
            accounts.append({"id": account["accountId"], "name": account.get("accountName", account["accountId"])})
    return sorted(accounts, key=lambda item: item["name"].lower())


def list_roles(sso_client, access_token: str, account_id: str) -> list[str]:
    """Devuelve los nombres de los roles (permission sets) de una cuenta."""
    paginator = sso_client.get_paginator("list_account_roles")
    roles = []
    for page in paginator.paginate(accessToken=access_token, accountId=account_id):
        roles.extend(role["roleName"] for role in page.get("roleList", []))
    return sorted(roles)


def get_role_credentials(sso_client, access_token: str, account_id: str, role: str) -> dict:
    """Pide credenciales temporales. La duración la define el permission set."""
    response = sso_client.get_role_credentials(accessToken=access_token, accountId=account_id, roleName=role)
    creds = response["roleCredentials"]
    return {
        "aws_access_key_id": creds["accessKeyId"],
        "aws_secret_access_key": creds["secretAccessKey"],
        "aws_session_token": creds["sessionToken"],
        "expiration": datetime.fromtimestamp(creds["expiration"] / 1000, tz=timezone.utc),
    }


# --- Selección --------------------------------------------------------------


def pick(options: list[str], label: str, input_fn: Callable[[str], str] = input) -> str:
    """Muestra un menú numerado y devuelve la opción elegida."""
    if not options:
        raise SwitchError(f"No hay opciones disponibles para: {label}")
    if len(options) == 1:
        print(f"? {label} › {options[0]} (única opción)")
        return options[0]
    for index, option in enumerate(options, start=1):
        print(f"  {index}) {option}")
    while True:
        answer = input_fn(f"? {label} (1-{len(options)}) › ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            print(f"? {label} › {options[int(answer) - 1]}")
            return options[int(answer) - 1]
        print("Opción inválida, intenta de nuevo.")


def resolve_account(accounts: list[dict], wanted: str | None, input_fn=input) -> dict:
    """Busca la cuenta por ID o nombre, o pregunta si no se indicó."""
    if wanted:
        for account in accounts:
            if wanted in (account["id"], account["name"]):
                return account
        raise SwitchError(f"No tienes acceso a la cuenta '{wanted}' o no existe.")
    labels = [f"{a['name']} ({a['id']})" for a in accounts]
    picked = pick(labels, "Cuenta", input_fn)
    return accounts[labels.index(picked)]


def resolve_role(roles: list[str], wanted: str | None, input_fn=input) -> str:
    if wanted:
        if wanted not in roles:
            raise SwitchError(f"El rol '{wanted}' no está asignado en esa cuenta. Disponibles: {', '.join(roles)}")
        return wanted
    return pick(roles, "Rol", input_fn)


# --- Perfiles y kubeconfig --------------------------------------------------


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def credentials_path() -> Path:
    custom = os.environ.get("AWS_SHARED_CREDENTIALS_FILE")
    return Path(custom).expanduser() if custom else Path.home() / ".aws" / "credentials"


def save_profile(profile: str, creds: dict, region: str | None, path: Path) -> None:
    """Guarda (o reemplaza) el perfil en el archivo de credenciales con permisos 600."""
    config = configparser.RawConfigParser()
    if path.exists():
        config.read(path)
    if config.has_section(profile):
        config.remove_section(profile)
    config.add_section(profile)
    for key in ("aws_access_key_id", "aws_secret_access_key", "aws_session_token"):
        config.set(profile, key, creds[key])
    config.set(profile, "x_security_token_expires", creds["expiration"].isoformat())
    if region:
        config.set(profile, "region", region)

    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        config.write(handle)
    os.chmod(path, 0o600)


def build_kubeconfig_command(cluster: str, profile: str, region: str) -> list[str]:
    return [
        "aws",
        "eks",
        "update-kubeconfig",
        "--name",
        cluster,
        "--profile",
        profile,
        "--region",
        region,
        "--alias",
        cluster,
    ]


def update_kubeconfig(cluster: str, profile: str, region: str, runner=subprocess.run) -> None:
    command = build_kubeconfig_command(cluster, profile, region)
    log.info("running: %s", " ".join(command))
    try:
        runner(command, check=True)
    except FileNotFoundError as exc:
        raise SwitchError("No se encontró el comando 'aws'. Instala AWS CLI v2.") from exc
    except subprocess.CalledProcessError as exc:
        raise SwitchError(f"Falló aws eks update-kubeconfig (código {exc.returncode}).") from exc


def format_remaining(expiration: datetime, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    minutes = max(int((expiration - now).total_seconds() // 60), 0)
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min" if hours else f"{minutes} min"


# --- CLI --------------------------------------------------------------------


class SpanishHelpFormatter(argparse.HelpFormatter):
    """Muestra 'uso:' en lugar de 'usage:' en la ayuda."""

    def add_usage(self, usage, actions, groups, prefix=None):
        return super().add_usage(usage, actions, groups, prefix or "uso: ")


def new_parser(**kwargs) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(formatter_class=SpanishHelpFormatter, add_help=False, **kwargs)
    parser._optionals.title = "opciones"
    parser.add_argument("-h", "--help", action="help", help="Muestra esta ayuda y termina.")
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = new_parser(
        prog="sso_switch.py",
        description=(
            "Obtiene credenciales temporales con IAM Identity Center (SSO) y las guarda "
            "como perfil en ~/.aws/credentials. Requiere haber ejecutado 'aws sso login'."
        ),
    )
    parser.add_argument(
        "--start-url",
        default=os.environ.get("SSO_START_URL"),
        help="AWS access portal URL (por defecto, la variable SSO_START_URL).",
    )
    parser.add_argument(
        "--sso-region",
        default=os.environ.get("SSO_REGION", "us-east-1"),
        help="Región donde está IAM Identity Center (por defecto, SSO_REGION o us-east-1).",
    )
    parser.add_argument("--account", help="ID o nombre de la cuenta. Si no lo indicas, se muestra un menú.")
    parser.add_argument("--role", help="Nombre del permission set. Si no lo indicas, se muestra un menú.")
    parser.add_argument("--profile-name", help="Nombre del perfil a guardar (por defecto: <cuenta>-<rol>).")
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-east-1"),
        help="Región por defecto del perfil (por defecto, AWS_REGION o us-east-1).",
    )
    parser.add_argument(
        "--cluster",
        default=os.environ.get("EKS_CLUSTER_NAME") or None,
        help=(
            "Cluster EKS para 'aws eks update-kubeconfig' (por defecto, EKS_CLUSTER_NAME). "
            "El contexto del kubeconfig queda con el mismo nombre del cluster."
        ),
    )
    parser.add_argument(
        "--sso-cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help=f"Carpeta del caché de SSO (por defecto, {DEFAULT_CACHE_DIR}).",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Muestra logs de depuración.")
    return parser


def main(argv: list[str] | None = None, input_fn: Callable[[str], str] = input) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")

    try:
        if not args.start_url:
            raise SwitchError("Falta la start URL. Usa --start-url o define SSO_START_URL.")
        token = cached_token(args.start_url, args.sso_cache_dir)
        client = build_sso_client(args.sso_region)

        account = resolve_account(list_accounts(client, token["access_token"]), args.account, input_fn)
        role = resolve_role(list_roles(client, token["access_token"], account["id"]), args.role, input_fn)
        creds = get_role_credentials(client, token["access_token"], account["id"], role)

        profile = args.profile_name or f"{slugify(account['name'])}-{slugify(role)}"
        path = credentials_path()
        save_profile(profile, creds, args.region, path)

        local_expiration = creds["expiration"].astimezone()
        print(f"✓ perfil {profile} · expira {local_expiration:%H:%M} (en {format_remaining(creds['expiration'])})")
        print(f"  {account['name']} ({account['id']}) · {role} · {path}")

        if args.cluster:
            update_kubeconfig(args.cluster, profile, args.region)
            print(f"✓ kubeconfig → {args.cluster}")

        print(f"\nPrueba: aws sts get-caller-identity --profile {profile}")
        return 0
    except SwitchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "UnauthorizedException":
            print("Error: el token de SSO no es válido o venció. Ejecuta: aws sso login", file=sys.stderr)
        else:
            print(f"Error de AWS ({code}): {exc}", file=sys.stderr)
        return 1
    except BotoCoreError as exc:
        print(f"Error de conexión con AWS: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelado.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
