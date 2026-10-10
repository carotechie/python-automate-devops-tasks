import json

import pods_check
from k8s_factories import container_status, fake_core_api, healthy_pod, pod, unschedulable_pod
from kubernetes.client.rest import ApiException
from kubernetes.config.config_exception import ConfigException


def broken_cluster():
    return [
        healthy_pod("web-1"),
        healthy_pod("web-2"),
        pod("broken-image-abc", phase="Pending", statuses=[container_status(waiting="ImagePullBackOff")]),
        pod("crashloop-xyz", statuses=[container_status(waiting="CrashLoopBackOff", restarts=7)]),
        unschedulable_pod("too-big-123"),
        pod("starting-1", phase="Pending", statuses=[container_status(waiting="ContainerCreating")]),
        pod("config-err", phase="Pending", statuses=[container_status(waiting="CreateContainerConfigError")]),
        pod("job-done", phase="Succeeded", statuses=[container_status(terminated="Completed")]),
    ]


def test_detects_each_problem_type():
    problems = {p.pod: p for p in pods_check.find_problems(broken_cluster())}
    assert problems["broken-image-abc"].reason == "ImagePullBackOff"
    assert problems["crashloop-xyz"].reason == "CrashLoopBackOff"
    assert problems["crashloop-xyz"].restarts == 7
    assert problems["too-big-123"].reason == "Unschedulable"
    assert "Insufficient cpu" in problems["too-big-123"].message
    assert problems["config-err"].reason == "CreateContainerConfigError"


def test_ignores_container_creating_and_healthy_pods():
    names = {p.pod for p in pods_check.find_problems(broken_cluster())}
    assert "starting-1" not in names
    assert "web-1" not in names
    assert "job-done" not in names


def test_err_image_pull_detected():
    problem = pods_check.detect_pod_problem(
        pod("x", phase="Pending", statuses=[container_status(waiting="ErrImagePull")])
    )
    assert problem.reason == "ErrImagePull"


def test_init_container_problem_detected():
    p = pod("init", phase="Pending")
    p.status.init_container_statuses = [container_status(name="migrate", waiting="CrashLoopBackOff", restarts=3)]
    problem = pods_check.detect_pod_problem(p)
    assert (problem.container, problem.reason, problem.restarts) == ("migrate", "CrashLoopBackOff", 3)


def test_summary_and_exit_code(capsys):
    code = pods_check.main([], core_api=fake_core_api(broken_cluster()))
    out = capsys.readouterr().out
    assert code == 1
    assert "4 de 8 pods con problemas" in out
    assert "CrashLoopBackOff" in out


def test_healthy_cluster_exit_zero(capsys):
    code = pods_check.main([], core_api=fake_core_api([healthy_pod("a"), healthy_pod("b")]))
    assert code == 0
    assert "0 de 2 pods con problemas" in capsys.readouterr().out


def test_cluster_without_pods(capsys):
    code = pods_check.main(["--namespace", "vacio"], core_api=fake_core_api([]))
    assert code == 0
    assert "No hay pods en el namespace 'vacio'" in capsys.readouterr().out


def test_namespace_flag_uses_namespaced_call():
    api = fake_core_api([healthy_pod("a")])
    pods_check.main(["-n", "lab"], core_api=api)
    api.list_namespaced_pod.assert_called_once_with("lab")
    api.list_pod_for_all_namespaces.assert_not_called()


def test_json_output(capsys):
    pods_check.main(["--output", "json"], core_api=fake_core_api(broken_cluster()))
    payload = json.loads(capsys.readouterr().out)
    assert payload["total"] == 8
    assert {p["reason"] for p in payload["problems"]} >= {"ImagePullBackOff", "Unschedulable"}


def test_api_error_exit_two(capsys):
    api = fake_core_api([])
    api.list_pod_for_all_namespaces.side_effect = ApiException(status=403, reason="Forbidden")
    assert pods_check.main([], core_api=api) == 2
    assert "403" in capsys.readouterr().err


def test_missing_kubeconfig_exit_two(monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise ConfigException("Invalid kube-config file. No configuration found.")

    monkeypatch.setattr(pods_check.config, "load_kube_config", boom)
    monkeypatch.setattr(pods_check.config, "load_incluster_config", boom)
    assert pods_check.main([]) == 2
    assert "kubeconfig" in capsys.readouterr().err


def test_context_defaults_to_kube_context_env(monkeypatch):
    monkeypatch.setenv("KUBE_CONTEXT", "kind-pyladies-lab")
    assert pods_check.build_parser().parse_args([]).context == "kind-pyladies-lab"
