import boto3
import seed_localstack
from moto import mock_aws


def test_refuses_non_local_endpoint(capsys):
    assert seed_localstack.main(["--endpoint-url", "https://ec2.us-east-1.amazonaws.com"]) == 1
    assert "no parece local" in capsys.readouterr().err


def test_is_local_endpoint():
    assert seed_localstack.is_local_endpoint("http://localhost:4566")
    assert seed_localstack.is_local_endpoint("http://127.0.0.1:4566")
    assert not seed_localstack.is_local_endpoint("https://example.com")


def test_seed_is_idempotent():
    with mock_aws():
        assert seed_localstack.seed(endpoint_url=None) == 3
        assert seed_localstack.seed(endpoint_url=None) == 0
        ec2 = boto3.client("ec2", region_name="eu-west-1")
        instance = ec2.describe_instances()["Reservations"][0]["Instances"][0]
    assert instance["State"]["Name"] == "stopped"
