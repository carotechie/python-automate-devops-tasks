import json

import boto3
import find_ec2
import pytest
from moto import mock_aws


def launch(region, name, env, state="running"):
    ec2 = boto3.client("ec2", region_name=region)
    image_id = ec2.describe_images(Owners=["amazon"])["Images"][0]["ImageId"]
    instance = ec2.run_instances(
        ImageId=image_id,
        InstanceType="t3.micro",
        MinCount=1,
        MaxCount=1,
        TagSpecifications=[
            {"ResourceType": "instance", "Tags": [{"Key": "Name", "Value": name}, {"Key": "env", "Value": env}]}
        ],
    )["Instances"][0]
    if state == "stopped":
        ec2.stop_instances(InstanceIds=[instance["InstanceId"]])
    return instance["InstanceId"]


@pytest.fixture
def fleet():
    with mock_aws():
        launch("us-east-1", "web-staging-01", "staging")
        launch("eu-west-1", "api-staging-01", "staging", state="stopped")
        launch("us-east-1", "worker-dev-01", "dev")
        launch("ap-south-1", "far-staging-01", "staging")
        yield


def test_parse_tag():
    assert find_ec2.parse_tag("env=staging") == ("env", "staging")
    assert find_ec2.parse_tag("note=a=b") == ("note", "a=b")


def test_parse_tag_invalid():
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        find_ec2.parse_tag("staging")


def test_build_filters():
    filters = find_ec2.build_filters([("env", "staging")], ["running"])
    assert filters == [
        {"Name": "tag:env", "Values": ["staging"]},
        {"Name": "instance-state-name", "Values": ["running"]},
    ]


def test_filters_by_tag_across_default_regions(fleet, capsys):
    assert find_ec2.main(["--tag", "env=staging", "--output", "json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    # ap-south-1 no está en las regiones por defecto.
    assert sorted(r["name"] for r in rows) == ["api-staging-01", "web-staging-01"]


def test_filters_by_state(fleet, capsys):
    find_ec2.main(["--tag", "env=staging", "--state", "running", "--output", "json"])
    rows = json.loads(capsys.readouterr().out)
    assert [r["name"] for r in rows] == ["web-staging-01"]


def test_custom_regions(fleet, capsys):
    find_ec2.main(["--regions", "ap-south-1", "--output", "json"])
    rows = json.loads(capsys.readouterr().out)
    assert [r["region"] for r in rows] == ["ap-south-1"]


def test_table_output(fleet, capsys):
    assert find_ec2.main(["--tag", "env=dev"]) == 0
    out = capsys.readouterr().out
    assert "worker-dev-01" in out
    assert "1 instancia(s) en 1 región(es)" in out


def test_no_results_message(fleet, capsys):
    assert find_ec2.main(["--tag", "env=prod"]) == 0
    assert "No se encontraron instancias" in capsys.readouterr().out


def test_collects_all_reservations(capsys):
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        image_id = ec2.describe_images(Owners=["amazon"])["Images"][0]["ImageId"]
        for _ in range(3):
            ec2.run_instances(ImageId=image_id, InstanceType="t3.micro", MinCount=5, MaxCount=5)
        rows = find_ec2.find_instances(boto3.Session(), ["us-east-1"], [])
    assert len(rows) == 15


def test_unknown_profile(capsys):
    assert find_ec2.main(["--profile", "no-existe"]) == 1
    assert "no-existe" in capsys.readouterr().err
