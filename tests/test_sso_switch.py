import configparser
import json
import os
import stat
from datetime import datetime, timedelta, timezone

import boto3
import pytest
import sso_switch
from botocore.stub import Stubber

START_URL = "https://d-1234567890.awsapps.com/start"
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def write_cache(cache_dir, name, start_url=START_URL, expires_at=None, token="token-123"):
    cache_dir.mkdir(parents=True, exist_ok=True)
    expires_at = expires_at or (datetime.now(timezone.utc) + timedelta(hours=1))
    payload = {
        "startUrl": start_url,
        "region": "us-east-1",
        "accessToken": token,
        "expiresAt": expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (cache_dir / f"{name}.json").write_text(json.dumps(payload))


@pytest.fixture
def stubbed_sso(monkeypatch):
    sso = boto3.client("sso", region_name="us-east-1")
    stubber = Stubber(sso)
    monkeypatch.setattr(sso_switch, "build_sso_client", lambda region: sso)
    with stubber:
        yield stubber


def add_happy_responses(stubber, expiration_ms):
    stubber.add_response(
        "list_accounts",
        {
            "accountList": [
                {"accountId": "111111111111", "accountName": "staging", "emailAddress": "staging@example.com"},
                {"accountId": "222222222222", "accountName": "prod", "emailAddress": "prod@example.com"},
            ]
        },
        {"accessToken": "token-123"},
    )
    stubber.add_response(
        "list_account_roles",
        {
            "roleList": [
                {"roleName": "ReadOnlyAccess", "accountId": "111111111111"},
                {"roleName": "AdministratorAccess", "accountId": "111111111111"},
            ]
        },
        {"accessToken": "token-123", "accountId": "111111111111"},
    )
    stubber.add_response(
        "get_role_credentials",
        {
            "roleCredentials": {
                "accessKeyId": "ASIAEXAMPLE",
                "secretAccessKey": "secret-example",
                "sessionToken": "session-example",
                "expiration": expiration_ms,
            }
        },
        {"accessToken": "token-123", "accountId": "111111111111", "roleName": "ReadOnlyAccess"},
    )


# --- Token -----------------------------------------------------------------


def test_parse_expiration_accepts_z_and_utc_suffix():
    assert sso_switch.parse_expiration("2026-10-10T12:00:00Z") == NOW
    assert sso_switch.parse_expiration("2026-10-10T12:00:00UTC") == NOW


def test_find_cached_token_returns_valid_token(tmp_path):
    write_cache(tmp_path, "a", expires_at=NOW + timedelta(hours=2))
    token = sso_switch.cached_token(START_URL + "/", tmp_path, now=NOW)
    assert token["access_token"] == "token-123"


def test_find_cached_token_ignores_other_start_urls_and_client_files(tmp_path):
    write_cache(tmp_path, "other", start_url="https://d-999.awsapps.com/start", expires_at=NOW + timedelta(hours=2))
    (tmp_path / "client.json").write_text(json.dumps({"clientId": "x", "expiresAt": "2027-01-01T00:00:00Z"}))
    (tmp_path / "broken.json").write_text("{not json")
    with pytest.raises(sso_switch.SwitchError, match="aws sso login"):
        sso_switch.cached_token(START_URL, tmp_path, now=NOW)


def test_expired_token_asks_for_login(tmp_path):
    write_cache(tmp_path, "old", expires_at=NOW - timedelta(minutes=1))
    with pytest.raises(sso_switch.SwitchError, match="aws sso login"):
        sso_switch.cached_token(START_URL, tmp_path, now=NOW)


def test_missing_cache_dir_asks_for_login(tmp_path):
    with pytest.raises(sso_switch.SwitchError, match="aws sso login"):
        sso_switch.cached_token(START_URL, tmp_path / "nope", now=NOW)


def test_picks_token_with_latest_expiration(tmp_path):
    write_cache(tmp_path, "a", expires_at=NOW + timedelta(hours=1), token="short")
    write_cache(tmp_path, "b", expires_at=NOW + timedelta(hours=5), token="long")
    assert sso_switch.cached_token(START_URL, tmp_path, now=NOW)["access_token"] == "long"


# --- Selección -------------------------------------------------------------


def test_choose_retries_until_valid_option(capsys):
    answers = iter(["9", "x", "2"])
    assert sso_switch.pick(["a", "b", "c"], "Rol", lambda _: next(answers)) == "b"
    assert capsys.readouterr().out.count("Opción inválida") == 2


def test_resolve_account_by_name_or_id():
    accounts = [{"id": "111111111111", "name": "staging"}]
    assert sso_switch.resolve_account(accounts, "staging")["id"] == "111111111111"
    assert sso_switch.resolve_account(accounts, "111111111111")["name"] == "staging"
    with pytest.raises(sso_switch.SwitchError):
        sso_switch.resolve_account(accounts, "prod")


def test_resolve_role_unknown_lists_available():
    with pytest.raises(sso_switch.SwitchError, match="ReadOnlyAccess"):
        sso_switch.resolve_role(["ReadOnlyAccess"], "Admin")


def test_kubeconfig_command_uses_profile():
    command = sso_switch.build_kubeconfig_command("lab", "staging-readonly", "us-east-1")
    assert command[:3] == ["aws", "eks", "update-kubeconfig"]
    assert "--profile" in command and "staging-readonly" in command


# --- main ------------------------------------------------------------------


def test_main_writes_profile_with_600_permissions(tmp_path, stubbed_sso, capsys):
    cache = tmp_path / "cache"
    write_cache(cache, "session")
    expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    add_happy_responses(stubbed_sso, int(expiration.timestamp() * 1000))

    code = sso_switch.main(
        [
            "--start-url",
            START_URL,
            "--sso-cache-dir",
            str(cache),
            "--account",
            "staging",
            "--role",
            "ReadOnlyAccess",
        ]
    )

    assert code == 0
    creds_file = tmp_path / "aws" / "credentials"
    assert stat.S_IMODE(os.stat(creds_file).st_mode) == 0o600
    config = configparser.RawConfigParser()
    config.read(creds_file)
    assert config.get("staging-readonlyaccess", "aws_access_key_id") == "ASIAEXAMPLE"
    assert config.get("staging-readonlyaccess", "region") == "us-east-1"
    assert "✓ perfil staging-readonlyaccess · expira" in capsys.readouterr().out
    stubbed_sso.assert_no_pending_responses()


def test_main_interactive_menu(tmp_path, stubbed_sso):
    cache = tmp_path / "cache"
    write_cache(cache, "session")
    expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    add_happy_responses(stubbed_sso, int(expiration.timestamp() * 1000))
    # Cuentas ordenadas: prod, staging -> "2". Roles ordenados: Administrator, ReadOnly -> "2".
    answers = iter(["2", "2"])

    code = sso_switch.main(
        ["--start-url", START_URL, "--sso-cache-dir", str(cache), "--profile-name", "demo"],
        input_fn=lambda _: next(answers),
    )
    assert code == 0


def test_main_keeps_other_profiles(tmp_path, stubbed_sso):
    creds_file = tmp_path / "aws" / "credentials"
    creds_file.parent.mkdir(parents=True)
    creds_file.write_text("[otro]\naws_access_key_id = AKIAOTHER\n")
    cache = tmp_path / "cache"
    write_cache(cache, "session")
    add_happy_responses(stubbed_sso, int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp() * 1000))

    sso_switch.main(
        ["--start-url", START_URL, "--sso-cache-dir", str(cache), "--account", "staging", "--role", "ReadOnlyAccess"]
    )

    config = configparser.RawConfigParser()
    config.read(creds_file)
    assert config.get("otro", "aws_access_key_id") == "AKIAOTHER"


def test_main_with_expired_token_fails(tmp_path, capsys):
    cache = tmp_path / "cache"
    write_cache(cache, "old", expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
    code = sso_switch.main(["--start-url", START_URL, "--sso-cache-dir", str(cache)])
    assert code == 1
    assert "aws sso login" in capsys.readouterr().err


def test_main_unauthorized_token_is_explained(tmp_path, stubbed_sso, capsys):
    cache = tmp_path / "cache"
    write_cache(cache, "session")
    stubbed_sso.add_client_error("list_accounts", service_error_code="UnauthorizedException", http_status_code=401)
    code = sso_switch.main(["--start-url", START_URL, "--sso-cache-dir", str(cache)])
    assert code == 1
    assert "aws sso login" in capsys.readouterr().err


def test_main_without_start_url_fails(capsys):
    assert sso_switch.main([]) == 1
    assert "SSO_START_URL" in capsys.readouterr().err


def test_main_runs_update_kubeconfig(tmp_path, stubbed_sso, monkeypatch):
    cache = tmp_path / "cache"
    write_cache(cache, "session")
    add_happy_responses(stubbed_sso, int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp() * 1000))
    calls = []
    monkeypatch.setattr(sso_switch, "update_kubeconfig", lambda *args: calls.append(args))

    code = sso_switch.main(
        [
            "--start-url",
            START_URL,
            "--sso-cache-dir",
            str(cache),
            "--account",
            "staging",
            "--role",
            "ReadOnlyAccess",
            "--cluster",
            "lab",
        ]
    )
    assert code == 0
    assert calls == [("lab", "staging-readonlyaccess", "us-east-1")]


def test_cluster_defaults_to_eks_cluster_name(monkeypatch):
    monkeypatch.setenv("EKS_CLUSTER_NAME", "eks-dev")
    assert sso_switch.build_parser().parse_args([]).cluster == "eks-dev"
    assert sso_switch.build_kubeconfig_command("eks-dev", "caro", "us-east-1")[-2:] == ["--alias", "eks-dev"]
