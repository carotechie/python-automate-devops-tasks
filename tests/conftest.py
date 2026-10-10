"""Configuración común: hace importables los scripts y aísla las credenciales."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for folder in (
    "01-acceso-multicuenta",
    "02-buscar-recursos",
    "03-pods-con-fallas",
    "04-triage-incidentes",
    "05-reportes",
    "lab",
):
    sys.path.insert(0, str(ROOT / folder))


@pytest.fixture(autouse=True)
def fake_aws_env(monkeypatch, tmp_path):
    """Credenciales falsas y archivos de AWS en una carpeta temporal."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "aws" / "credentials"))
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "aws" / "config"))
    for var in (
        "AWS_PROFILE",
        "AWS_ENDPOINT_URL",
        "HUB_PROFILE",
        "HUB_ACCOUNTS",
        "SSO_START_URL",
        "EKS_CLUSTER_NAME",
        "KUBE_CONTEXT",
    ):
        monkeypatch.delenv(var, raising=False)
