#!/usr/bin/env python3
"""Busca instancias EC2 en varias regiones filtrando por tags y estado.

Es de solo lectura: solo llama a ec2:DescribeInstances.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, ProfileNotFound
from tabulate import tabulate

log = logging.getLogger("find_ec2")

DEFAULT_REGIONS = ["us-east-1", "eu-west-1", "sa-east-1"]
STATES = ["pending", "running", "stopping", "stopped", "shutting-down", "terminated"]


class SearchError(Exception):
    """Error esperado que se muestra a la persona sin traceback."""


def parse_tag(value: str) -> tuple[str, str]:
    """Convierte 'env=staging' en ('env', 'staging')."""
    key, sep, tag_value = value.partition("=")
    if not sep or not key:
        raise argparse.ArgumentTypeError(f"Tag inválido '{value}'. Usa el formato clave=valor.")
    return key, tag_value


def parse_regions(value: str) -> list[str]:
    regions = [region.strip() for region in value.split(",") if region.strip()]
    if not regions:
        raise argparse.ArgumentTypeError("Indica al menos una región.")
    return regions


def build_filters(tags: list[tuple[str, str]], states: list[str] | None) -> list[dict]:
    filters = [{"Name": f"tag:{key}", "Values": [value]} for key, value in tags]
    if states:
        filters.append({"Name": "instance-state-name", "Values": states})
    return filters


def tags_to_dict(tags: list[dict] | None) -> dict:
    return {tag["Key"]: tag["Value"] for tag in tags or []}


def describe_region(session, region: str, filters: list[dict], endpoint_url: str | None) -> list[dict]:
    """Devuelve las instancias de una región como diccionarios planos."""
    client = session.client("ec2", region_name=region, endpoint_url=endpoint_url)
    paginator = client.get_paginator("describe_instances")
    rows = []
    for page in paginator.paginate(Filters=filters):
        for reservation in page.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                tags = tags_to_dict(instance.get("Tags"))
                launch_time = instance.get("LaunchTime")
                rows.append(
                    {
                        "region": region,
                        "instance_id": instance["InstanceId"],
                        "name": tags.get("Name", "-"),
                        "type": instance.get("InstanceType", "-"),
                        "state": instance.get("State", {}).get("Name", "-"),
                        "private_ip": instance.get("PrivateIpAddress", "-"),
                        "launch_time": launch_time.isoformat() if launch_time else "-",
                        "tags": tags,
                    }
                )
    return rows


def find_instances(session, regions: list[str], filters: list[dict], endpoint_url: str | None = None) -> list[dict]:
    rows = []
    for region in regions:
        log.debug("searching region %s", region)
        rows.extend(describe_region(session, region, filters, endpoint_url))
    return sorted(rows, key=lambda row: (row["region"], row["name"], row["instance_id"]))


def render_table(rows: list[dict]) -> str:
    columns = ["region", "instance_id", "name", "type", "state", "private_ip", "launch_time"]
    headers = ["Región", "ID", "Nombre", "Tipo", "Estado", "IP privada", "Creada"]
    return tabulate([[row[col] for col in columns] for row in rows], headers=headers, tablefmt="github")


def render_json(rows: list[dict]) -> str:
    return json.dumps(rows, indent=2, ensure_ascii=False)


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
        prog="find_ec2.py",
        description="Busca instancias EC2 en varias regiones filtrando por tags y estado.",
    )
    parser.add_argument(
        "--regions",
        type=parse_regions,
        default=DEFAULT_REGIONS,
        help=f"Regiones separadas por coma (por defecto: {','.join(DEFAULT_REGIONS)}).",
    )
    parser.add_argument(
        "--tag",
        type=parse_tag,
        action="append",
        default=[],
        help="Filtro por tag en formato clave=valor. Puedes repetirlo: --tag env=staging --tag team=web.",
    )
    parser.add_argument(
        "--state",
        choices=STATES,
        action="append",
        help="Filtra por estado. Puedes repetirlo. Por defecto, todos.",
    )
    parser.add_argument("--profile", help="Perfil de AWS a usar.")
    parser.add_argument(
        "--output", choices=["table", "json"], default="table", help="Formato de salida (por defecto: table)."
    )
    parser.add_argument(
        "--endpoint-url",
        default=os.environ.get("AWS_ENDPOINT_URL"),
        help="Endpoint alternativo, por ejemplo http://localhost:4566 para LocalStack.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Muestra logs de depuración.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")

    try:
        session = boto3.Session(profile_name=args.profile)
        filters = build_filters(args.tag, args.state)
        rows = find_instances(session, args.regions, filters, args.endpoint_url)
    except ProfileNotFound:
        print(f"Error: no existe el perfil '{args.profile}'.", file=sys.stderr)
        return 1
    except NoCredentialsError:
        print(
            "Error: no hay credenciales de AWS. Usa --profile o, en el laboratorio, source lab/lab.env", file=sys.stderr
        )
        return 1
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        print(f"Error de AWS ({code}): {exc.response.get('Error', {}).get('Message', exc)}", file=sys.stderr)
        return 1
    except BotoCoreError as exc:
        print(f"Error de conexión con AWS: {exc}", file=sys.stderr)
        return 1

    if args.output == "json":
        print(render_json(rows))
        return 0

    if not rows:
        print(f"No se encontraron instancias en {', '.join(args.regions)} con esos filtros.")
        return 0
    print(render_table(rows))
    print(f"\n{len(rows)} instancia(s) en {len({row['region'] for row in rows})} región(es).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
