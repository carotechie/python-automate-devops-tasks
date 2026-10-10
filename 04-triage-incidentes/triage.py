#!/usr/bin/env python3
"""Junta la información inicial de un incidente en Kubernetes y genera un resumen.

Para una app (deployment) reúne: estado del deployment, pods que no están
listos, últimos eventos Warning y el log anterior del primer pod caído.
Escribe incident-summary-<app>-<timestamp>.md y lo imprime.

No arregla nada: es de solo lectura y te ahorra los primeros minutos.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.config.config_exception import ConfigException

log = logging.getLogger("triage")

REVISION_ANNOTATION = "deployment.kubernetes.io/revision"
CHANGE_CAUSE_ANNOTATION = "kubernetes.io/change-cause"
VERSION_LABELS = ("app.kubernetes.io/version", "version")
EPOCH = datetime.min.replace(tzinfo=timezone.utc)


class TriageError(Exception):
    """Error esperado que se muestra a la persona sin traceback."""


def load_config(context: str | None = None, kubeconfig: str | None = None) -> None:
    try:
        config.load_kube_config(config_file=kubeconfig, context=context)
    except ConfigException:
        if context or kubeconfig:
            raise
        config.load_incluster_config()


def fmt_time(value: datetime | None) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if value else "-"


def time_ago(value: datetime | None, now: datetime) -> str:
    if not value:
        return ""
    minutes = max(int((now - value).total_seconds() // 60), 0)
    if minutes < 60:
        return f"hace {minutes} min"
    hours = minutes // 60
    return f"hace {hours} h" if hours < 48 else f"hace {hours // 24} días"


def selector_from_labels(labels: dict | None) -> str:
    return ",".join(f"{key}={value}" for key, value in sorted((labels or {}).items()))


# --- Deployment -------------------------------------------------------------


def get_deployment(apps_api, namespace: str, app: str):
    try:
        return apps_api.read_namespaced_deployment(app, namespace)
    except ApiException as exc:
        if exc.status == 404:
            raise TriageError(f"No existe el deployment '{app}' en el namespace '{namespace}'.") from exc
        raise


def get_owned_replica_sets(apps_api, deployment) -> list:
    """ReplicaSets que pertenecen al deployment (uno por revisión)."""
    selector = selector_from_labels(deployment.spec.selector.match_labels)
    replica_sets = apps_api.list_namespaced_replica_set(deployment.metadata.namespace, label_selector=selector).items
    return [
        rs
        for rs in replica_sets
        if any(
            o.kind == "Deployment" and o.name == deployment.metadata.name for o in rs.metadata.owner_references or []
        )
    ]


def get_last_rollout(deployment, replica_sets: list) -> datetime | None:
    """Fecha del ReplicaSet de la revisión actual; si no se encuentra, la del deployment."""
    revision = (deployment.metadata.annotations or {}).get(REVISION_ANNOTATION)
    for rs in replica_sets:
        if (rs.metadata.annotations or {}).get(REVISION_ANNOTATION) == revision:
            return rs.metadata.creation_timestamp
    return deployment.metadata.creation_timestamp


def get_version(deployment) -> str:
    """Versión declarada en las labels del template, si la hay."""
    labels = (deployment.spec.template.metadata.labels if deployment.spec.template.metadata else None) or {}
    return next((labels[key] for key in VERSION_LABELS if key in labels), "-")


def summarize_deployment(deployment, replica_sets: list) -> dict:
    status = deployment.status
    annotations = deployment.metadata.annotations or {}
    return {
        "name": deployment.metadata.name,
        "desired": deployment.spec.replicas or 0,
        "ready": status.ready_replicas or 0,
        "updated": status.updated_replicas or 0,
        "available": status.available_replicas or 0,
        "images": [c.image for c in deployment.spec.template.spec.containers],
        "version": get_version(deployment),
        "revision": annotations.get(REVISION_ANNOTATION, "-"),
        "change_cause": annotations.get(CHANGE_CAUSE_ANNOTATION, "-"),
        "last_rollout": get_last_rollout(deployment, replica_sets),
    }


# --- Pods -------------------------------------------------------------------


def pod_reason(pod) -> str:
    for cs in pod.status.container_statuses or []:
        if cs.state and cs.state.waiting and cs.state.waiting.reason:
            return cs.state.waiting.reason
        if cs.state and cs.state.terminated and cs.state.terminated.reason:
            return cs.state.terminated.reason
    for condition in pod.status.conditions or []:
        if condition.type == "PodScheduled" and condition.status != "True":
            return condition.reason or "Unschedulable"
    return pod.status.phase or "Unknown"


def is_pod_ready(pod) -> bool:
    for condition in pod.status.conditions or []:
        if condition.type == "Ready":
            return condition.status == "True"
    return False


def get_unready_pods(core_api, namespace: str, selector: str) -> list[dict]:
    pods = core_api.list_namespaced_pod(namespace, label_selector=selector).items
    unready = []
    for pod in pods:
        if is_pod_ready(pod):
            continue
        statuses = pod.status.container_statuses or []
        unready.append(
            {
                "name": pod.metadata.name,
                "phase": pod.status.phase,
                "reason": pod_reason(pod),
                "restarts": sum(cs.restart_count or 0 for cs in statuses),
                "container": statuses[0].name if statuses else pod.spec.containers[0].name,
                "node": pod.spec.node_name or "-",
            }
        )
    # Primero los que más se reinician: suelen ser los que tienen log anterior.
    return sorted(unready, key=lambda p: (-p["restarts"], p["name"]))


# --- Eventos y logs ---------------------------------------------------------


def event_time(event) -> datetime:
    return (
        event.last_timestamp
        or getattr(event, "event_time", None)
        or event.first_timestamp
        or event.metadata.creation_timestamp
        or EPOCH
    )


def is_related(object_name: str, app: str, rs_names: list[str]) -> bool:
    """El deployment, sus ReplicaSets y sus pods (<replicaset>-<id>)."""
    if object_name == app or object_name in rs_names:
        return True
    return any(object_name.startswith(f"{rs}-") for rs in rs_names)


def get_warning_events(core_api, namespace: str, app: str, rs_names: list[str], limit: int) -> list[dict]:
    events = core_api.list_namespaced_event(namespace, field_selector="type=Warning").items
    related = [e for e in events if is_related(e.involved_object.name or "", app, rs_names)]
    related.sort(key=event_time, reverse=True)
    return [
        {
            "time": event_time(e),
            "object": f"{e.involved_object.kind}/{e.involved_object.name}",
            "reason": e.reason or "-",
            "message": (e.message or "").strip(),
            "count": e.count or 1,
        }
        for e in related[:limit]
    ]


def get_previous_logs(core_api, namespace: str, pod: str, container: str, tail: int) -> tuple[str, str]:
    """Devuelve (origen, log). Usa el log anterior; si no existe, el actual."""
    try:
        text = core_api.read_namespaced_pod_log(pod, namespace, container=container, previous=True, tail_lines=tail)
        return "previous", text
    except ApiException as exc:
        if exc.status != 400:
            raise
        log.debug("no previous log for %s, falling back to current", pod)
    try:
        text = core_api.read_namespaced_pod_log(pod, namespace, container=container, tail_lines=tail)
        return "current", text
    except ApiException:
        return "none", ""


# --- Markdown ---------------------------------------------------------------


def escape_cell(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ")


def build_markdown(report: dict) -> str:
    dep = report["deployment"]
    rollout_ago = time_ago(dep["last_rollout"], report["generated_at"])
    status_icon = "OK" if dep["ready"] >= dep["desired"] else "DEGRADADO"
    lines = [
        f"# Resumen de incidente: {report['app']}",
        "",
        f"- **Namespace:** `{report['namespace']}`",
        f"- **Generado:** {fmt_time(report['generated_at'])}",
        f"- **Estado:** {status_icon} ({dep['ready']}/{dep['desired']} réplicas listas)",
        "",
        "> Este resumen no arregla nada: junta los datos para que empieces a investigar.",
        "",
        "## Deployment",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Réplicas listas / deseadas | {dep['ready']} / {dep['desired']} |",
        f"| Actualizadas / disponibles | {dep['updated']} / {dep['available']} |",
        f"| Imagen | {', '.join(f'`{image}`' for image in dep['images'])} |",
        f"| Versión | {dep['version']} |",
        f"| Revisión | {dep['revision']} · {escape_cell(dep['change_cause'])} |",
        f"| Último rollout | {fmt_time(dep['last_rollout'])} ({rollout_ago}) |",
        "",
        "## Pods que no están listos",
        "",
    ]
    if report["pods"]:
        lines += ["| Pod | Fase | Razón | Reinicios | Nodo |", "|---|---|---|---|---|"]
        lines += [
            f"| {p['name']} | {p['phase']} | {p['reason']} | {p['restarts']} | {p['node']} |" for p in report["pods"]
        ]
    else:
        lines.append("Todos los pods están listos.")

    lines += ["", "## Últimos eventos Warning", ""]
    if report["events"]:
        lines += ["| Hora | Objeto | Razón | Veces | Mensaje |", "|---|---|---|---|---|"]
        lines += [
            f"| {fmt_time(e['time'])} | {e['object']} | {e['reason']} | {e['count']} | {escape_cell(e['message'])} |"
            for e in report["events"]
        ]
    else:
        lines.append("No hay eventos Warning recientes.")

    lines += ["", "## Logs", ""]
    logs = report["logs"]
    if logs:
        origin = "anterior (`previous=True`)" if logs["origin"] == "previous" else "actual"
        lines.append(f"Últimas {report['tail']} líneas del log {origin} de `{logs['pod']}`:")
        lines += ["", "```text", logs["text"].rstrip() or "(vacío)", "```"]
    else:
        lines.append("No hay pods caídos de los que leer logs.")

    lines += [
        "",
        "## Próximos pasos sugeridos",
        "",
        f"- `kubectl -n {report['namespace']} describe deployment {report['app']}`",
        f"- `kubectl -n {report['namespace']} rollout history deployment/{report['app']}`",
    ]
    if report["pods"]:
        lines.append(f"- `kubectl -n {report['namespace']} describe pod {report['pods'][0]['name']}`")
    return "\n".join(lines) + "\n"


def write_report(markdown: str, app: str, output_dir: Path, now: datetime) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"incident-summary-{app}-{now:%Y%m%d-%H%M%S}.md"
    path.write_text(markdown, encoding="utf-8")
    return path


def collect(core_api, apps_api, namespace: str, app: str, tail: int, max_events: int, now: datetime) -> dict:
    deployment = get_deployment(apps_api, namespace, app)
    replica_sets = get_owned_replica_sets(apps_api, deployment)
    rs_names = [rs.metadata.name for rs in replica_sets]
    selector = selector_from_labels(deployment.spec.selector.match_labels)
    pods = get_unready_pods(core_api, namespace, selector)

    logs = None
    if pods:
        first = pods[0]
        origin, text = get_previous_logs(core_api, namespace, first["name"], first["container"], tail)
        logs = {"pod": first["name"], "origin": origin, "text": text}

    return {
        "app": app,
        "namespace": namespace,
        "generated_at": now,
        "tail": tail,
        "deployment": summarize_deployment(deployment, replica_sets),
        "pods": pods,
        "events": get_warning_events(core_api, namespace, app, rs_names, max_events),
        "logs": logs,
    }


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
        prog="triage.py",
        description=(
            "Genera un resumen Markdown con el estado de un deployment, sus pods caídos, "
            "los eventos Warning y el log anterior. No modifica nada."
        ),
    )
    parser.add_argument("-n", "--namespace", required=True, help="Namespace de la app.")
    parser.add_argument("-a", "--app", required=True, help="Nombre del deployment.")
    parser.add_argument("--tail", type=int, default=20, help="Líneas de log a incluir (por defecto: 20).")
    parser.add_argument("--events", type=int, default=10, help="Cantidad máxima de eventos (por defecto: 10).")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("."), help="Carpeta donde guardar el resumen (por defecto: la actual)."
    )
    parser.add_argument(
        "--context",
        default=os.environ.get("KUBE_CONTEXT") or None,
        help="Contexto del kubeconfig a usar (por defecto, KUBE_CONTEXT o el contexto actual).",
    )
    parser.add_argument("--kubeconfig", help="Ruta al kubeconfig.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Muestra logs de depuración.")
    return parser


def main(argv: list[str] | None = None, core_api=None, apps_api=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    now = datetime.now(timezone.utc)

    try:
        if core_api is None or apps_api is None:
            load_config(args.context, args.kubeconfig)
            core_api, apps_api = client.CoreV1Api(), client.AppsV1Api()
        report = collect(core_api, apps_api, args.namespace, args.app, args.tail, args.events, now)
    except TriageError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ConfigException as exc:
        print(f"Error: no se pudo cargar el kubeconfig ({exc}).", file=sys.stderr)
        return 1
    except ApiException as exc:
        print(f"Error de la API de Kubernetes ({exc.status}): {exc.reason}", file=sys.stderr)
        return 1

    markdown = build_markdown(report)
    path = write_report(markdown, args.app, args.output_dir, now)
    print(markdown)
    print(f"Resumen guardado en {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
