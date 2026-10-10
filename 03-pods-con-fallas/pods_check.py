#!/usr/bin/env python3
"""Detecta pods con fallas en un cluster de Kubernetes.

Reporta pods en Pending que no están arrancando y contenedores en waiting con
razones problemáticas. Termina con exit code 1 si encuentra problemas, para
poder usarlo en CI o en un cron.

Es de solo lectura: solo lista pods.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.config.config_exception import ConfigException
from tabulate import tabulate

log = logging.getLogger("pods_check")

PROBLEM_REASONS = {
    "CrashLoopBackOff",
    "ImagePullBackOff",
    "ErrImagePull",
    "CreateContainerConfigError",
    "CreateContainerError",
    "InvalidImageName",
}
STARTING_REASONS = {"ContainerCreating", "PodInitializing"}


@dataclass
class PodProblem:
    namespace: str
    pod: str
    container: str
    reason: str
    restarts: int
    message: str = ""


def load_config(context: str | None = None, kubeconfig: str | None = None) -> None:
    """Carga el kubeconfig local o, si corre dentro del cluster, la config in-cluster."""
    try:
        config.load_kube_config(config_file=kubeconfig, context=context)
    except ConfigException:
        if context or kubeconfig:
            raise
        log.debug("kubeconfig not found, trying in-cluster config")
        config.load_incluster_config()


def list_pods(core_api, namespace: str | None) -> list:
    if namespace:
        return core_api.list_namespaced_pod(namespace).items
    return core_api.list_pod_for_all_namespaces().items


def container_statuses(pod) -> list:
    status = pod.status
    return list(status.init_container_statuses or []) + list(status.container_statuses or [])


def total_restarts(pod) -> int:
    return sum(cs.restart_count or 0 for cs in container_statuses(pod))


def scheduling_reason(pod) -> tuple[str, str]:
    """Devuelve la razón por la que un pod Pending no se pudo programar."""
    for condition in pod.status.conditions or []:
        if condition.type == "PodScheduled" and condition.status != "True":
            return condition.reason or "Pending", condition.message or ""
    return "Pending", ""


def detect_pod_problem(pod) -> PodProblem | None:
    """Devuelve el problema principal del pod, o None si está bien o arrancando."""
    namespace, name = pod.metadata.namespace, pod.metadata.name
    restarts = total_restarts(pod)
    starting = False

    for cs in container_statuses(pod):
        waiting = cs.state.waiting if cs.state else None
        if not waiting:
            continue
        if waiting.reason in PROBLEM_REASONS:
            return PodProblem(namespace, name, cs.name, waiting.reason, restarts, waiting.message or "")
        if waiting.reason in STARTING_REASONS:
            starting = True

    if pod.status.phase == "Pending" and not starting:
        reason, message = scheduling_reason(pod)
        return PodProblem(namespace, name, "-", reason, restarts, message)
    return None


def find_problems(pods: list) -> list[PodProblem]:
    problems = [problem for pod in pods if (problem := detect_pod_problem(pod))]
    return sorted(problems, key=lambda p: (p.namespace, p.pod))


def summary_line(problem_count: int, total: int) -> str:
    return f"{problem_count} de {total} pods con problemas"


def render_table(problems: list[PodProblem]) -> str:
    rows = [[p.namespace, p.pod, p.container, p.reason, p.restarts] for p in problems]
    return tabulate(rows, headers=["Namespace", "Pod", "Contenedor", "Razón", "Reinicios"], tablefmt="github")


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
        prog="pods_check.py",
        description=(
            "Lista pods con fallas (Pending, CrashLoopBackOff, ImagePullBackOff, ...). "
            "Devuelve exit code 1 si encuentra alguno."
        ),
    )
    parser.add_argument("-n", "--namespace", help="Namespace a revisar. Por defecto, todos.")
    parser.add_argument(
        "--context",
        default=os.environ.get("KUBE_CONTEXT") or None,
        help="Contexto del kubeconfig a usar (por defecto, KUBE_CONTEXT o el contexto actual).",
    )
    parser.add_argument("--kubeconfig", help="Ruta al kubeconfig (por defecto, ~/.kube/config o KUBECONFIG).")
    parser.add_argument(
        "--output", choices=["table", "json"], default="table", help="Formato de salida (por defecto: table)."
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Muestra logs de depuración.")
    return parser


def main(argv: list[str] | None = None, core_api=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")

    try:
        if core_api is None:
            load_config(args.context, args.kubeconfig)
            core_api = client.CoreV1Api()
        pods = list_pods(core_api, args.namespace)
    except ConfigException as exc:
        print(
            f"Error: no se pudo cargar el kubeconfig ({exc}). ¿Creaste el cluster con 'make lab-up'?", file=sys.stderr
        )
        return 2
    except ApiException as exc:
        print(f"Error de la API de Kubernetes ({exc.status}): {exc.reason}", file=sys.stderr)
        return 2
    except Exception as exc:  # urllib3 connection errors, etc.
        print(f"Error: no se pudo conectar al cluster ({exc.__class__.__name__}: {exc}).", file=sys.stderr)
        return 2

    problems = find_problems(pods)

    if args.output == "json":
        payload = {"total": len(pods), "problems": [asdict(p) for p in problems]}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif not pods:
        scope = f"el namespace '{args.namespace}'" if args.namespace else "el cluster"
        print(f"No hay pods en {scope}.")
    else:
        if problems:
            print(render_table(problems))
            print()
        print(summary_line(len(problems), len(pods)))

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
