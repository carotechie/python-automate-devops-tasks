"""Fábricas de objetos de la API de Kubernetes para los tests."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from kubernetes import client


def ts(minutes: int = 0) -> datetime:
    return datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc).replace(minute=minutes)


def container_status(name="app", waiting=None, restarts=0, ready=False, terminated=None, message=None):
    state = client.V1ContainerState(
        waiting=client.V1ContainerStateWaiting(reason=waiting, message=message) if waiting else None,
        running=None if waiting or terminated else client.V1ContainerStateRunning(started_at=ts()),
        terminated=client.V1ContainerStateTerminated(exit_code=1, reason=terminated) if terminated else None,
    )
    return client.V1ContainerStatus(
        name=name, image="busybox:1.36", image_id="", ready=ready, restart_count=restarts, state=state
    )


def pod(name, namespace="lab", phase="Running", statuses=None, conditions=None, labels=None):
    return client.V1Pod(
        metadata=client.V1ObjectMeta(name=name, namespace=namespace, labels=labels or {}),
        spec=client.V1PodSpec(containers=[client.V1Container(name="app", image="busybox:1.36")], node_name="node-1"),
        status=client.V1PodStatus(phase=phase, container_statuses=statuses, conditions=conditions),
    )


def healthy_pod(name, namespace="lab", labels=None):
    return pod(
        name,
        namespace,
        statuses=[container_status(ready=True)],
        conditions=[client.V1PodCondition(type="Ready", status="True")],
        labels=labels,
    )


def unschedulable_pod(name, namespace="lab"):
    return pod(
        name,
        namespace,
        phase="Pending",
        conditions=[
            client.V1PodCondition(
                type="PodScheduled",
                status="False",
                reason="Unschedulable",
                message="0/1 nodes are available: 1 Insufficient cpu.",
            )
        ],
    )


def pod_list(*pods):
    return client.V1PodList(items=list(pods))


def fake_core_api(pods):
    api = MagicMock()
    api.list_pod_for_all_namespaces.return_value = pod_list(*pods)
    api.list_namespaced_pod.return_value = pod_list(*pods)
    return api
