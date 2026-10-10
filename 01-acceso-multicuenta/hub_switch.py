#!/usr/bin/env python3
"""Asume un rol en una cuenta destino desde una cuenta puente (hub).

Usa el perfil de la cuenta puente (HUB_PROFILE), llama a sts:AssumeRole con la
duración pedida y guarda las credenciales como perfil <env>-<rol>.

    python hub_switch.py prod ReadOnly 30m

El ID de cada ambiente sale de HUB_ACCOUNTS (dev=111111111111,prod=333333333333)
o de --account.

Es de solo lectura sobre AWS: no crea ni modifica recursos.
"""

from __future__ import annotations

import argparse
import configparser
import getpass
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, ProfileNotFound

log = logging.getLogger("hub_switch")

MIN_DURATION = 15 * 60
MAX_DURATION = 12 * 60 * 60
CHAINING_MAX_DURATION = 60 * 60

DURATION_PATTERN = re.compile(r"^(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?$")
ACCOUNT_PATTERN = re.compile(r"^\d{12}$")


class SwitchError(Exception):
    """Error esperado que se muestra a la persona sin traceback."""


# --- Validaciones -----------------------------------------------------------


def to_seconds(value: str) -> int:
    """Convierte '30m', '1h' o '1h30m' a segundos."""
    match = DURATION_PATTERN.match(value.strip().lower())
    if not value.strip() or not match or not any(match.groupdict().values()):
        raise SwitchError(f"Duración inválida: '{value}'. Usa formatos como 30m, 1h o 1h30m.")
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    return hours * 3600 + minutes * 60


def validate_duration(seconds: int) -> None:
    if not MIN_DURATION <= seconds <= MAX_DURATION:
        raise SwitchError(f"La duración debe estar entre 15m y 12h (pediste {format_seconds(seconds)}).")


def validate_account(account_id: str) -> None:
    if not ACCOUNT_PATTERN.match(account_id):
        raise SwitchError(f"El ID de cuenta '{account_id}' debe tener 12 dígitos.")


def parse_accounts(text: str | None) -> dict[str, str]:
    """Convierte 'dev=111111111111,prod=333333333333' en un diccionario."""
    accounts = {}
    for item in (text or "").split(","):
        env, sep, account_id = item.strip().partition("=")
        if not item.strip():
            continue
        if not sep or not env:
            raise SwitchError(f"Entrada inválida en HUB_ACCOUNTS: '{item.strip()}'. Usa env=123456789012.")
        accounts[env.strip()] = account_id.strip()
    return accounts


def resolve_account(env: str, accounts: dict[str, str], override: str | None) -> str:
    account_id = override or accounts.get(env)
    if not account_id:
        known = ", ".join(sorted(accounts)) or "ninguno"
        raise SwitchError(
            f"No sé qué cuenta es '{env}'. Agrégala a HUB_ACCOUNTS (ambientes conocidos: {known}) o usa --account."
        )
    validate_account(account_id)
    return account_id


def format_remaining(expiration: datetime, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    minutes = max(round((expiration - now).total_seconds() / 60), 0)
    hours, minutes = divmod(minutes, 60)
    if hours and minutes:
        return f"{hours} h {minutes} min"
    return f"{hours} h" if hours else f"{minutes} min"


def format_seconds(seconds: int) -> str:
    hours, rest = divmod(seconds, 3600)
    minutes = rest // 60
    if hours and minutes:
        return f"{hours}h{minutes}m"
    return f"{hours}h" if hours else f"{minutes}m"


# --- STS --------------------------------------------------------------------


def build_session(profile: str | None, region: str | None):
    return boto3.Session(profile_name=profile, region_name=region)


def get_caller_arn(sts_client) -> str:
    return sts_client.get_caller_identity()["Arn"]


def is_role_chaining(caller_arn: str) -> bool:
    """Si ya estás usando un rol asumido, el siguiente AssumeRole es role chaining."""
    return ":assumed-role/" in caller_arn


def check_chaining_limit(caller_arn: str, seconds: int) -> None:
    if is_role_chaining(caller_arn) and seconds > CHAINING_MAX_DURATION:
        raise SwitchError(
            "Tu identidad en la cuenta puente ya es un rol asumido "
            f"({caller_arn}).\nEso es role chaining y AWS limita la sesión a 1 h. "
            f"Pediste {format_seconds(seconds)}: pide 1h o menos, "
            "o entra a la cuenta puente con un usuario IAM o SSO directo."
        )


def build_role_arn(account_id: str, role: str) -> str:
    return f"arn:aws:iam::{account_id}:role/{role}"


def assume_role(
    sts_client,
    role_arn: str,
    seconds: int,
    session_name: str,
    mfa_serial: str | None = None,
    mfa_code: str | None = None,
) -> dict:
    params = {"RoleArn": role_arn, "RoleSessionName": session_name, "DurationSeconds": seconds}
    if mfa_serial:
        if not mfa_code:
            raise SwitchError("Indicaste --mfa-serial pero falta --mfa-code.")
        params.update(SerialNumber=mfa_serial, TokenCode=mfa_code)
    creds = sts_client.assume_role(**params)["Credentials"]
    expiration = creds["Expiration"]
    if expiration.tzinfo is None:
        expiration = expiration.replace(tzinfo=timezone.utc)
    return {
        "aws_access_key_id": creds["AccessKeyId"],
        "aws_secret_access_key": creds["SecretAccessKey"],
        "aws_session_token": creds["SessionToken"],
        "expiration": expiration,
    }


def explain_client_error(exc: ClientError, role_arn: str, seconds: int) -> str:
    code = exc.response.get("Error", {}).get("Code", "")
    message = exc.response.get("Error", {}).get("Message", "")
    if code == "AccessDenied":
        return (
            f"AccessDenied al asumir {role_arn}. Revisa que la trust policy confíe en la "
            "cuenta puente, que tu política permita sts:AssumeRole y, si aplica, el MFA."
        )
    if code == "ValidationError" and "DurationSeconds" in message:
        return (
            f"AWS rechazó la duración {format_seconds(seconds)}. Revisa el MaxSessionDuration "
            "del rol destino (por defecto es 1 h)."
        )
    return f"Error de AWS ({code}): {message}"


# --- Perfil -----------------------------------------------------------------


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


def default_session_name() -> str:
    user = re.sub(r"[^\w+=,.@-]", "-", getpass.getuser())
    return f"hub-switch-{user}"[:64]


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
        prog="hub_switch.py",
        description=(
            "Asume un rol en una cuenta destino usando el perfil de la cuenta puente "
            "y guarda las credenciales como perfil <env>-<rol>."
        ),
    )
    parser.add_argument("env", help="Ambiente destino, por ejemplo dev, staging o prod.")
    parser.add_argument("role", nargs="?", default="ReadOnly", help="Rol en la cuenta destino (por defecto: ReadOnly).")
    parser.add_argument(
        "duration",
        nargs="?",
        default="1h",
        help="Duración de la sesión: 30m, 1h, 1h30m... (15m a 12h, por defecto 1h).",
    )
    parser.add_argument(
        "--account",
        help="ID (12 dígitos) de la cuenta destino. Si no lo indicas, se busca el ambiente en HUB_ACCOUNTS.",
    )
    parser.add_argument(
        "--hub-profile",
        default=os.environ.get("HUB_PROFILE"),
        help="Perfil de la cuenta puente (por defecto, la variable HUB_PROFILE).",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-east-1"),
        help="Región por defecto del perfil generado (por defecto, AWS_REGION o us-east-1).",
    )
    parser.add_argument("--profile-name", help="Nombre del perfil a guardar (por defecto: <env>-<rol>).")
    parser.add_argument(
        "--session-name", default=default_session_name(), help="RoleSessionName que queda en CloudTrail."
    )
    parser.add_argument("--mfa-serial", help="ARN del dispositivo MFA, si la trust policy lo exige.")
    parser.add_argument("--mfa-code", help="Código de 6 dígitos del MFA.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Muestra logs de depuración.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")

    role_arn = ""
    seconds = 0
    try:
        account_id = resolve_account(args.env, parse_accounts(os.environ.get("HUB_ACCOUNTS")), args.account)
        seconds = to_seconds(args.duration)
        validate_duration(seconds)

        sts = build_session(args.hub_profile, args.region).client("sts")
        caller_arn = get_caller_arn(sts)
        log.debug("hub identity: %s", caller_arn)
        check_chaining_limit(caller_arn, seconds)

        role_arn = build_role_arn(account_id, args.role)
        creds = assume_role(sts, role_arn, seconds, args.session_name, args.mfa_serial, args.mfa_code)

        profile = args.profile_name or f"{args.env}-{args.role}".lower()
        path = credentials_path()
        save_profile(profile, creds, args.region, path)

        local_expiration = creds["expiration"].astimezone()
        print(f"✓ {args.env}/{args.role} · vence en {format_remaining(creds['expiration'])} ({local_expiration:%H:%M})")
        print(f"  perfil '{profile}' guardado en {path}")
        print(f"  rol: {role_arn}")
        print(f"\nPrueba: aws sts get-caller-identity --profile {profile}")
        return 0
    except SwitchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ProfileNotFound:
        print(f"Error: no existe el perfil '{args.hub_profile}'. Revisa HUB_PROFILE o --hub-profile.", file=sys.stderr)
        return 1
    except NoCredentialsError:
        print("Error: no hay credenciales para la cuenta puente. Configura HUB_PROFILE.", file=sys.stderr)
        return 1
    except ClientError as exc:
        print(f"Error: {explain_client_error(exc, role_arn, seconds)}", file=sys.stderr)
        return 1
    except BotoCoreError as exc:
        print(f"Error de conexión con AWS: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
