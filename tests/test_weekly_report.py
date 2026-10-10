import json

import boto3
import pytest
import weekly_report
from k8s_factories import fake_core_api, healthy_pod, pod
from moto import mock_aws


@pytest.fixture
def fleet():
    with mock_aws():
        for region, env in [("us-east-1", "staging"), ("eu-west-1", "staging"), ("us-east-1", "dev")]:
            ec2 = boto3.client("ec2", region_name=region)
            image_id = ec2.describe_images(Owners=["amazon"])["Images"][0]["ImageId"]
            ec2.run_instances(
                ImageId=image_id,
                InstanceType="t3.micro",
                MinCount=1,
                MaxCount=1,
                TagSpecifications=[{"ResourceType": "instance", "Tags": [{"Key": "env", "Value": env}]}],
            )
        yield


def staging_pods():
    return [healthy_pod("web-1", labels={"env": "staging"}), pod("checkout-1", phase="Pending")]


def test_markdown_report(fleet, capsys):
    code = weekly_report.main(["--env", "staging", "--env", "dev"], core_api=fake_core_api(staging_pods()))
    out = capsys.readouterr().out
    assert code == 0
    assert "# Reporte semanal de infraestructura" in out
    assert "| Ambiente" in out
    assert "TOTAL" in out


def test_json_counts(fleet, capsys):
    weekly_report.main(["--env", "staging", "--env", "dev", "--format", "json"], core_api=fake_core_api(staging_pods()))
    rows = {r["env"]: r for r in json.loads(capsys.readouterr().out)}
    assert rows["staging"]["ec2_total"] == 2
    assert rows["dev"]["ec2_total"] == 1
    assert rows["staging"]["pods_total"] == 2
    assert rows["staging"]["pods_not_running"] == 1
    assert rows["TOTAL"]["ec2_total"] == 3


def test_csv_to_file_without_k8s(fleet, tmp_path):
    target = tmp_path / "reports" / "weekly.csv"
    code = weekly_report.main(["--env", "staging", "--format", "csv", "--skip-k8s", "--output-file", str(target)])
    assert code == 0
    lines = target.read_text().splitlines()
    assert lines[0] == "env,ec2_total,ec2_running"
    assert lines[1] == "staging,2,2"


def test_ignores_terminated_instances():
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        image_id = ec2.describe_images(Owners=["amazon"])["Images"][0]["ImageId"]
        ids = [
            i["InstanceId"]
            for i in ec2.run_instances(ImageId=image_id, InstanceType="t3.micro", MinCount=2, MaxCount=2)["Instances"]
        ]
        ec2.terminate_instances(InstanceIds=ids[:1])
        counts = weekly_report.count_instances(boto3.Session(), ["us-east-1"], [], None)
    assert counts == {"ec2_total": 1, "ec2_running": 1}


def test_pods_filtered_by_env_label():
    api = fake_core_api([])
    weekly_report.count_pods(api, "env=staging")
    api.list_pod_for_all_namespaces.assert_called_once_with(label_selector="env=staging")


def test_kubernetes_error_suggests_skip(fleet, monkeypatch, capsys):
    def boom(context):
        raise RuntimeError("no cluster")

    monkeypatch.setattr(weekly_report, "build_core_api", boom)
    assert weekly_report.main(["--env", "staging"]) == 1
    assert "--skip-k8s" in capsys.readouterr().err


def test_context_per_env_like_the_slide(fleet, capsys):
    clusters = {
        "staging": fake_core_api([healthy_pod("a"), healthy_pod("b"), healthy_pod("c")]),
        "dev": fake_core_api([]),
    }
    code = weekly_report.main(
        ["--env", "staging", "--env", "dev", "--context-per-env", "--format", "json"], api_factory=clusters.__getitem__
    )
    rows = {r["env"]: r for r in json.loads(capsys.readouterr().out)}
    assert code == 0
    assert rows["staging"]["pods_total"] == 3
    assert rows["dev"]["pods_total"] == 0
    clusters["staging"].list_pod_for_all_namespaces.assert_called_once_with()
