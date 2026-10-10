#!/usr/bin/env python3
"""Genera un reporte semanal de instancias EC2 y pods por ambiente.

Cada ambiente se identifica por el tag `env` (en EC2) y la label `env` (en
Kubernetes). Con --profile-per-env, cada ambiente usa el perfil de AWS que se
llama igual y se cuentan todas sus instancias.

Es de solo lectura: solo lista instancias y pods.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3
import pandas as pd
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, ProfileNotFound

log = logging.getLogger("weekly_report")

DEFAULT_REGIONS = ["us-east-1", "eu-west-1", "sa-east-1"]
COLUMNS = {
    "env": "Ambiente",
    "ec2_total": "EC2 total",
    "ec2_running": "EC2 en ejecución",
    "pods_total": "Pods",
    "pods_not_running": "Pods sin Running",
}


class ReportError(Exception):
    """Error esperado que se muestra a la persona sin traceback."""


# --- EC2 --------------------------------------------------------------------


def count_instances(session, regions: list[str], filters: list[dict], endpoint_url: str | None) -> dict:
    """Cuenta instancias (sin las terminadas) y cuántas están en running."""
    total = running = 0
    for region in regions:
        ec2 = session.client("ec2", region_name=region, endpoint_url=endpoint_url)
        for page in ec2.get_paginator("describe_instances").paginate(Filters=filters):
            for reservation in page.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    state = instance.get("State", {}).get("Name")
                    if state == "terminated":
                        continue
                    total += 1
                    running += state == "running"
    return {"ec2_total": total, "ec2_running": running}


def ec2_for_env(env: str, args) -> dict:
    if args.profile_per_env:
        session = boto3.Session(profile_name=env)
        filters: list[dict] = []
    else:
        session = boto3.Session(profile_name=args.profile)
        filters = [{"Name": f"tag:{args.tag_key}", "Values": [env]}]
    return count_instances(session, args.regions, filters, args.endpoint_url)


# --- Kubernetes -------------------------------------------------------------


def build_core_api(context: str | None):
    from kubernetes import client, config

    config.load_kube_config(context=context)
    return client.CoreV1Api()


def count_pods(core_api, label_selector: str | None) -> dict:
    """Cuenta pods del cluster; con label_selector, solo los de ese ambiente."""
    if label_selector:
        pods = core_api.list_pod_for_all_namespaces(label_selector=label_selector).items
    else:
        pods = core_api.list_pod_for_all_namespaces().items
    not_running = sum(1 for pod in pods if pod.status.phase not in ("Running", "Succeeded"))
    return {"pods_total": len(pods), "pods_not_running": not_running}


# --- Reporte ----------------------------------------------------------------


def collect_rows(envs: list[str], args, core_api, api_factory=None) -> list[dict]:
    """Una fila por ambiente. Con --context-per-env, cada ambiente usa su propio cluster."""
    api_factory = api_factory or build_core_api
    rows = []
    for env in envs:
        log.info("collecting %s", env)
        row = {"env": env, **ec2_for_env(env, args)}
        if args.skip_k8s:
            pass
        elif args.context_per_env:
            row.update(count_pods(api_factory(env), None))
        elif core_api is not None:
            row.update(count_pods(core_api, f"{args.tag_key}={env}"))
        rows.append(row)
    return rows


def build_dataframe(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame = frame[[col for col in COLUMNS if col in frame.columns]]
    totals = {col: frame[col].sum() if col != "env" else "TOTAL" for col in frame.columns}
    return pd.concat([frame, pd.DataFrame([totals])], ignore_index=True)


def render(frame: pd.DataFrame, fmt: str, generated_at: datetime, regions: list[str]) -> str:
    if fmt == "csv":
        return frame.to_csv(index=False)
    if fmt == "json":
        return frame.to_json(orient="records", indent=2, force_ascii=False) + "\n"
    table = frame.rename(columns=COLUMNS).to_markdown(index=False)
    return (
        f"# Reporte semanal de infraestructura\n\n"
        f"- **Generado:** {generated_at:%Y-%m-%d %H:%M} UTC\n"
        f"- **Regiones:** {', '.join(regions)}\n\n"
        f"{table}\n"
    )


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
        prog="weekly_report.py",
        description="Cuenta instancias EC2 y pods por ambiente y genera un reporte en Markdown, CSV o JSON.",
    )
    parser.add_argument(
        "--env",
        dest="envs",
        action="append",
        required=True,
        help="Ambiente a incluir. Repítelo: --env staging --env dev.",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "csv", "json"],
        default="markdown",
        help="Formato del reporte (por defecto: markdown).",
    )
    parser.add_argument("--output-file", type=Path, help="Archivo de salida. Si no lo indicas, se imprime.")
    parser.add_argument(
        "--regions",
        type=lambda v: [r.strip() for r in v.split(",") if r.strip()],
        default=DEFAULT_REGIONS,
        help=f"Regiones separadas por coma (por defecto: {','.join(DEFAULT_REGIONS)}).",
    )
    parser.add_argument(
        "--tag-key",
        default="env",
        help="Tag de EC2 y label de Kubernetes que identifica el ambiente (por defecto: env).",
    )
    parser.add_argument("--profile", help="Perfil de AWS a usar para todos los ambientes.")
    parser.add_argument(
        "--profile-per-env", action="store_true", help="Usa un perfil de AWS con el mismo nombre de cada ambiente."
    )
    parser.add_argument(
        "--endpoint-url",
        default=os.environ.get("AWS_ENDPOINT_URL"),
        help="Endpoint alternativo, por ejemplo http://localhost:4566 para LocalStack.",
    )
    parser.add_argument(
        "--context",
        default=os.environ.get("KUBE_CONTEXT") or None,
        help="Contexto del kubeconfig a usar (por defecto, KUBE_CONTEXT o el contexto actual).",
    )
    parser.add_argument(
        "--context-per-env",
        action="store_true",
        help="Cuenta todos los pods del contexto de kubeconfig que se llama como cada ambiente.",
    )
    parser.add_argument("--skip-k8s", action="store_true", help="No cuenta pods (útil en CI sin cluster).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Muestra logs de depuración.")
    return parser


def main(argv: list[str] | None = None, core_api=None, api_factory=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")

    try:
        if core_api is None and not (args.skip_k8s or args.context_per_env):
            core_api = build_core_api(args.context)
        rows = collect_rows(args.envs, args, core_api, api_factory)
    except ProfileNotFound as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except NoCredentialsError:
        print(
            "Error: no hay credenciales de AWS. Usa --profile o, en el laboratorio, source lab/lab.env", file=sys.stderr
        )
        return 1
    except (ClientError, BotoCoreError) as exc:
        print(f"Error de AWS: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # kubeconfig ausente, cluster caído, etc.
        print(
            f"Error al consultar Kubernetes ({exc.__class__.__name__}): {exc}. Usa --skip-k8s si no tienes cluster.",
            file=sys.stderr,
        )
        return 1

    output = render(build_dataframe(rows), args.format, datetime.now(timezone.utc), args.regions)
    if args.output_file:
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        args.output_file.write_text(output, encoding="utf-8")
        print(f"Reporte guardado en {args.output_file}")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
