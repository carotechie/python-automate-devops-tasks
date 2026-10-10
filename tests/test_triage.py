from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
import triage
from k8s_factories import container_status, healthy_pod, pod, pod_list, ts
from kubernetes import client
from kubernetes.client.rest import ApiException

NOW = datetime(2026, 10, 6, 9, 30, tzinfo=timezone.utc)


def deployment(ready=1, desired=3):
    return client.V1Deployment(
        metadata=client.V1ObjectMeta(
            name="checkout",
            namespace="lab",
            creation_timestamp=ts(0),
            annotations={
                "deployment.kubernetes.io/revision": "4",
                "kubernetes.io/change-cause": "v2.4.1: mueve el carrito a postgres",
            },
        ),
        spec=client.V1DeploymentSpec(
            replicas=desired,
            selector=client.V1LabelSelector(match_labels={"app": "checkout"}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": "checkout", "app.kubernetes.io/version": "v2.4.1"}),
                spec=client.V1PodSpec(containers=[client.V1Container(name="checkout", image="busybox:1.36")]),
            ),
        ),
        status=client.V1DeploymentStatus(ready_replicas=ready, updated_replicas=desired, available_replicas=ready),
    )


def replica_set(revision, created):
    return client.V1ReplicaSet(
        metadata=client.V1ObjectMeta(
            name=f"checkout-{revision}abc",
            creation_timestamp=created,
            annotations={"deployment.kubernetes.io/revision": revision},
            owner_references=[
                client.V1OwnerReference(api_version="apps/v1", kind="Deployment", name="checkout", uid="u")
            ],
        ),
        spec=client.V1ReplicaSetSpec(selector=client.V1LabelSelector(match_labels={"app": "checkout"})),
    )


def event(name, reason, message, minute, kind="Pod"):
    return client.CoreV1Event(
        metadata=client.V1ObjectMeta(name=f"{name}.{minute}"),
        involved_object=client.V1ObjectReference(kind=kind, name=name),
        reason=reason,
        message=message,
        type="Warning",
        count=3,
        last_timestamp=ts(minute),
    )


@pytest.fixture
def apis():
    apps = MagicMock()
    apps.read_namespaced_deployment.return_value = deployment()
    apps.list_namespaced_replica_set.return_value = client.V1ReplicaSetList(
        items=[replica_set("3", ts(5)), replica_set("4", ts(20))]
    )
    core = MagicMock()
    crashing = pod(
        "checkout-4abc-1", statuses=[container_status(name="checkout", waiting="CrashLoopBackOff", restarts=6)]
    )
    crashing.status.conditions = [client.V1PodCondition(type="Ready", status="False")]
    pending = pod(
        "checkout-4abc-2", phase="Pending", statuses=[container_status(name="checkout", waiting="ContainerCreating")]
    )
    core.list_namespaced_pod.return_value = pod_list(healthy_pod("checkout-4abc-0"), crashing, pending)
    core.list_namespaced_event.return_value = client.CoreV1EventList(
        items=[
            event("checkout-4abc-1", "BackOff", "Back-off restarting failed container", 25),
            event("checkout-4abc-1", "Unhealthy", "Readiness probe failed", 22),
            event("checkout-api-zzz", "BackOff", "otra app", 29),
            event("web-1", "BackOff", "no relacionado", 28),
        ]
    )
    core.read_namespaced_pod_log.return_value = "connecting to postgres\nFATAL: database unreachable, exiting\n"
    return core, apps


def test_collect_report(apis):
    core, apps = apis
    report = triage.collect(core, apps, "lab", "checkout", 20, 10, NOW)

    assert report["deployment"]["ready"] == 1
    assert report["deployment"]["desired"] == 3
    assert report["deployment"]["last_rollout"] == ts(20)
    assert [p["name"] for p in report["pods"]] == ["checkout-4abc-1", "checkout-4abc-2"]
    assert [e["reason"] for e in report["events"]] == ["BackOff", "Unhealthy"]  # más reciente primero
    assert report["logs"]["origin"] == "previous"
    core.read_namespaced_pod_log.assert_called_once_with(
        "checkout-4abc-1", "lab", container="checkout", previous=True, tail_lines=20
    )
    core.list_namespaced_pod.assert_called_once_with("lab", label_selector="app=checkout")


def test_main_writes_markdown(apis, tmp_path, capsys):
    core, apps = apis
    code = triage.main(["-n", "lab", "-a", "checkout", "--output-dir", str(tmp_path)], core_api=core, apps_api=apps)
    assert code == 0
    files = list(tmp_path.glob("incident-summary-checkout-*.md"))
    assert len(files) == 1
    text = files[0].read_text()
    for section in ("## Deployment", "## Pods que no están listos", "## Últimos eventos Warning", "## Logs"):
        assert section in text
    assert "1 / 3" in text
    assert "FATAL: database unreachable" in text
    assert "DEGRADADO" in text
    assert "hace " in text
    assert "| Versión | v2.4.1 |" in text
    assert "mueve el carrito a postgres" in text
    assert "Resumen guardado en" in capsys.readouterr().out


def test_time_ago():
    assert triage.time_ago(ts(18), NOW) == "hace 12 min"
    assert triage.time_ago(None, NOW) == ""


def test_falls_back_to_current_log_when_no_previous(apis):
    core, apps = apis
    core.read_namespaced_pod_log.side_effect = [ApiException(status=400, reason="Bad Request"), "current log"]
    report = triage.collect(core, apps, "lab", "checkout", 20, 10, NOW)
    assert report["logs"] == {"pod": "checkout-4abc-1", "origin": "current", "text": "current log"}


def test_healthy_deployment(apis):
    core, apps = apis
    apps.read_namespaced_deployment.return_value = deployment(ready=1, desired=1)
    core.list_namespaced_pod.return_value = pod_list(healthy_pod("checkout-4abc-0"))
    core.list_namespaced_event.return_value = client.CoreV1EventList(items=[])
    report = triage.collect(core, apps, "lab", "checkout", 20, 10, NOW)
    markdown = triage.build_markdown(report)
    assert "Todos los pods están listos." in markdown
    assert "No hay eventos Warning recientes." in markdown
    core.read_namespaced_pod_log.assert_not_called()


def test_missing_deployment(apis, capsys, tmp_path):
    core, apps = apis
    apps.read_namespaced_deployment.side_effect = ApiException(status=404, reason="Not Found")
    code = triage.main(["-n", "lab", "-a", "nope", "--output-dir", str(tmp_path)], core_api=core, apps_api=apps)
    assert code == 1
    assert "No existe el deployment 'nope'" in capsys.readouterr().err
    assert not list(tmp_path.iterdir())


def test_is_related_ignores_apps_with_same_prefix():
    rs_names = ["checkout-4abc"]
    assert triage.is_related("checkout", "checkout", rs_names)
    assert triage.is_related("checkout-4abc", "checkout", rs_names)
    assert triage.is_related("checkout-4abc-x1y2z", "checkout", rs_names)
    assert not triage.is_related("checkout-api-7d9f-x1", "checkout", rs_names)


def test_events_limit(apis):
    core, apps = apis
    events = triage.get_warning_events(core, "lab", "checkout", ["checkout-4abc"], limit=1)
    assert len(events) == 1
