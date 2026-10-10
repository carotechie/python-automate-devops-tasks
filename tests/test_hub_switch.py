import configparser
import json
import os
import stat

import boto3
import hub_switch
import pytest
from moto import mock_aws

TARGET_ACCOUNT = "123456789012"  # cuenta por defecto de moto, ficticia


@pytest.fixture
def aws():
    with mock_aws():
        iam = boto3.client("iam", region_name="us-east-1")
        trust = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::111111111111:root"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
        iam.create_role(RoleName="ReadOnly", AssumeRolePolicyDocument=json.dumps(trust), MaxSessionDuration=43200)
        yield


# --- Duraciones ------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("30m", 1800), ("1h", 3600), ("1h30m", 5400), ("12h", 43200), ("15m", 900), ("2H", 7200)],
)
def test_parse_duration(text, seconds):
    assert hub_switch.to_seconds(text) == seconds


@pytest.mark.parametrize("text", ["", "90", "1d", "h", "1h 30m", "-1h", "m30"])
def test_parse_duration_rejects_invalid(text):
    with pytest.raises(hub_switch.SwitchError, match="Duración inválida"):
        hub_switch.to_seconds(text)


@pytest.mark.parametrize("seconds", [0, 14 * 60, 12 * 3600 + 60, 13 * 3600])
def test_validate_duration_out_of_range(seconds):
    with pytest.raises(hub_switch.SwitchError, match="entre 15m y 12h"):
        hub_switch.validate_duration(seconds)


def test_format_seconds():
    assert hub_switch.format_seconds(5400) == "1h30m"
    assert hub_switch.format_seconds(3600) == "1h"
    assert hub_switch.format_seconds(1800) == "30m"


# --- Role chaining ---------------------------------------------------------


def test_detects_role_chaining():
    assert hub_switch.is_role_chaining("arn:aws:sts::111111111111:assumed-role/Hub/caro")
    assert not hub_switch.is_role_chaining("arn:aws:iam::111111111111:user/caro")


def test_chaining_rejects_more_than_one_hour():
    with pytest.raises(hub_switch.SwitchError, match="role chaining"):
        hub_switch.check_chaining_limit("arn:aws:sts::111111111111:assumed-role/Hub/caro", 7200)


def test_chaining_allows_one_hour():
    hub_switch.check_chaining_limit("arn:aws:sts::111111111111:assumed-role/Hub/caro", 3600)


def test_user_identity_allows_twelve_hours():
    hub_switch.check_chaining_limit("arn:aws:iam::111111111111:user/caro", 43200)


# --- main ------------------------------------------------------------------


def test_main_assumes_role_and_writes_profile(aws, tmp_path, capsys):
    code = hub_switch.main(["staging", "ReadOnly", "2h", "--account", TARGET_ACCOUNT])

    assert code == 0
    creds_file = tmp_path / "aws" / "credentials"
    assert stat.S_IMODE(os.stat(creds_file).st_mode) == 0o600
    config = configparser.RawConfigParser()
    config.read(creds_file)
    assert config.has_section("staging-readonly")
    assert config.get("staging-readonly", "aws_access_key_id").startswith("ASIA")
    out = capsys.readouterr().out
    assert "✓ staging/ReadOnly · vence en 2 h" in out

    # Las credenciales guardadas funcionan con boto3.
    os.environ.pop("AWS_ACCESS_KEY_ID")
    os.environ.pop("AWS_SECRET_ACCESS_KEY")
    os.environ.pop("AWS_SESSION_TOKEN")
    os.environ.pop("AWS_SECURITY_TOKEN")
    arn = boto3.Session(profile_name="staging-readonly").client("sts").get_caller_identity()["Arn"]
    assert ":assumed-role/ReadOnly/" in arn


def test_main_rejects_chaining_over_one_hour(aws, monkeypatch, capsys):
    monkeypatch.setattr(hub_switch, "get_caller_arn", lambda sts: "arn:aws:sts::111111111111:assumed-role/Hub/caro")
    code = hub_switch.main(["staging", "ReadOnly", "1h30m", "--account", TARGET_ACCOUNT])
    assert code == 1
    assert "role chaining" in capsys.readouterr().err


def test_main_chaining_with_one_hour_works(aws, monkeypatch):
    monkeypatch.setattr(hub_switch, "get_caller_arn", lambda sts: "arn:aws:sts::111111111111:assumed-role/Hub/caro")
    assert hub_switch.main(["staging", "ReadOnly", "1h", "--account", TARGET_ACCOUNT]) == 0


def test_main_rejects_duration_out_of_range(capsys):
    assert hub_switch.main(["dev", "ReadOnly", "13h", "--account", TARGET_ACCOUNT]) == 1
    assert "entre 15m y 12h" in capsys.readouterr().err


def test_main_rejects_invalid_account(capsys):
    assert hub_switch.main(["dev", "--account", "1234"]) == 1
    assert "12 dígitos" in capsys.readouterr().err


def test_main_unknown_hub_profile(capsys):
    code = hub_switch.main(["dev", "--account", TARGET_ACCOUNT, "--hub-profile", "no-existe"])
    assert code == 1
    assert "no-existe" in capsys.readouterr().err


def test_mfa_serial_requires_code(aws):
    sts = boto3.client("sts", region_name="us-east-1")
    with pytest.raises(hub_switch.SwitchError, match="--mfa-code"):
        hub_switch.assume_role(sts, "arn:aws:iam::123456789012:role/ReadOnly", 3600, "s", "arn:aws:iam::1:mfa/caro")


def test_explain_access_denied():
    from botocore.exceptions import ClientError

    error = ClientError({"Error": {"Code": "AccessDenied", "Message": "nope"}}, "AssumeRole")
    assert "trust policy" in hub_switch.explain_client_error(error, "arn:aws:iam::1:role/X", 3600)


# --- HUB_ACCOUNTS ----------------------------------------------------------


def test_parse_accounts():
    accounts = hub_switch.parse_accounts("dev=111111111111, prod=333333333333,")
    assert accounts == {"dev": "111111111111", "prod": "333333333333"}


def test_parse_accounts_invalid():
    with pytest.raises(hub_switch.SwitchError, match="HUB_ACCOUNTS"):
        hub_switch.parse_accounts("dev:111111111111")


def test_main_uses_hub_accounts_like_the_slide(aws, monkeypatch, capsys):
    monkeypatch.setenv("HUB_ACCOUNTS", f"dev=111111111111,prod={TARGET_ACCOUNT}")
    assert hub_switch.main(["prod", "ReadOnly", "30m"]) == 0
    assert "✓ prod/ReadOnly · vence en 30 min" in capsys.readouterr().out


def test_main_unknown_env(monkeypatch, capsys):
    monkeypatch.setenv("HUB_ACCOUNTS", "dev=111111111111")
    assert hub_switch.main(["qa"]) == 1
    err = capsys.readouterr().err
    assert "'qa'" in err and "dev" in err


def test_defaults_are_readonly_and_one_hour():
    args = hub_switch.build_parser().parse_args(["dev"])
    assert (args.role, args.duration) == ("ReadOnly", "1h")
