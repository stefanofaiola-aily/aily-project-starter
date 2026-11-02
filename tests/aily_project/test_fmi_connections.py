"""Profile isolation and verified read-only connection ownership, without AWS."""

import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from click.testing import CliRunner

from aily_project.cli import cli
from aily_project.services.fmi.connections import (
    ProfileCloudProvider,
    profile_provider,
    read_connections,
)
from aily_project.services.fmi.models import Inputs, Snapshot
from aily_project.services.fmi.policy import Policy

pytestmark = pytest.mark.unit
MODULE = "aily_project.services.fmi.connections"
RUNNER = "aily_project.services.fmi.runner"


def test_provider_uses_explicit_profile_without_changing_environment(monkeypatch):
    monkeypatch.setenv("AILY_CLOUD_PROVIDER", "aws")
    monkeypatch.setenv("AWS_REGION", "eu-central-1")
    monkeypatch.setenv("AWS_PROFILE", "tenant-test")
    with patch(f"{MODULE}.Session") as session:
        provider = profile_provider("shared-test")
    session.assert_called_once_with(
        profile_name="shared-test", region_name="eu-central-1"
    )
    assert provider is not None
    assert provider.get_session() is session.return_value
    assert os.environ["AWS_PROFILE"] == "tenant-test"


def test_secrets_client_keeps_profile_even_for_cross_region_secret():
    session = MagicMock()
    provider = ProfileCloudProvider("eu-central-1", session=session)
    with patch(f"{MODULE}.Session") as default_session:
        provider.get_secrets_client("eu-west-1")
        provider.get_secrets_client()
    default_session.assert_not_called()
    assert [c.kwargs["region_name"] for c in session.client.call_args_list] == [
        "eu-west-1",
        "eu-central-1",
    ]
    assert all(c.args == ("secretsmanager",) for c in session.client.call_args_list)


def test_no_profile_keeps_published_default_cloud_route():
    with patch(f"{MODULE}.Session") as session:
        assert profile_provider(None) is None
    session.assert_not_called()


@pytest.mark.parametrize("missing", ["region", "aws"])
def test_invalid_profile_settings_fail_before_cloud(monkeypatch, missing):
    monkeypatch.setenv("AILY_CLOUD_PROVIDER", "aws" if missing == "region" else "gcp")
    monkeypatch.delenv("AWS_REGION", raising=False)
    with patch(f"{MODULE}.Session") as session, pytest.raises(ValueError):
        profile_provider("profile")
    session.assert_not_called()


@pytest.mark.parametrize("separate", [True, False])
def test_connections_keep_profiles_roles_and_read_only_separate(monkeypatch, separate):
    monkeypatch.setenv("AWS_PROFILE", "tenant-test")
    if separate:
        monkeypatch.setenv("FMI_SHARED_AWS_PROFILE", "shared-test")
    else:
        monkeypatch.delenv("FMI_SHARED_AWS_PROFILE", raising=False)
    tenant_dal, shared_dal = MagicMock(), MagicMock()
    with (
        patch(f"{MODULE}.Dal", side_effect=[tenant_dal, shared_dal]) as dal,
        patch(f"{MODULE}.profile_provider") as provider,
        patch(f"{MODULE}.verify_read_only") as verify,
        read_connections() as (light, shared),
    ):
        assert light is tenant_dal.db.__enter__.return_value
        assert shared is shared_dal.shared_db.__enter__.return_value
        assert [c.args[0] for c in verify.call_args_list] == [light, shared]
    assert [c.args[0] for c in provider.call_args_list] == [
        "tenant-test",
        "shared-test" if separate else "tenant-test",
    ]
    configs = [
        dal.call_args_list[0].kwargs["db_config"],
        dal.call_args_list[1].kwargs["shared_db_config"],
    ]
    assert configs[0].db_user == "ro"
    assert all(
        c.session_settings == {"default_transaction_read_only": "on"} for c in configs
    )
    tenant_dal.shared_db.__enter__.assert_not_called()
    shared_dal.db.__enter__.assert_not_called()
    tenant_dal.db.__exit__.assert_called_once()
    shared_dal.shared_db.__exit__.assert_called_once()


def test_unverified_connection_is_never_yielded_and_both_close():
    tenant_dal, shared_dal = MagicMock(), MagicMock()
    with (
        patch(f"{MODULE}.Dal", side_effect=[tenant_dal, shared_dal]),
        patch(f"{MODULE}.profile_provider"),
        patch(f"{MODULE}.verify_read_only", side_effect=[None, ValueError("off")]),
        pytest.raises(ValueError, match="off"),
        read_connections(),
    ):
        pytest.fail("Unsafe clients must not reach the caller")
    tenant_dal.db.__exit__.assert_called_once()
    shared_dal.shared_db.__exit__.assert_called_once()


def test_preflight_initializes_once_and_reads_only_session_metadata():
    events = []
    light, shared = MagicMock(), MagicMock()
    for client in (light, shared):
        client.fetch_data_as_df.return_value = pd.DataFrame(
            [{"database_role": "test", "transaction_read_only": "on"}]
        )
    with (
        patch(f"{RUNNER}.initialize", side_effect=lambda: events.append("settings")),
        patch(f"{RUNNER}.read_connections") as connections,
    ):
        connections.return_value.__enter__.side_effect = lambda: (
            events.append("connections") or (light, shared)
        )
        result = CliRunner().invoke(cli, ["fmi", "check-connections"])
    assert result.exit_code == 0, result.output
    assert events == ["settings", "connections"]
    for client in (light, shared):
        query = client.fetch_data_as_df.call_args.args[0]
        assert query.startswith("SELECT ") and " FROM " not in query


def test_extract_initializes_before_connection_factory(tmp_path):
    inputs = tmp_path / "inputs.json"
    inputs.write_text("{}")
    events = []
    with (
        patch(
            f"{RUNNER}.initialize",
            side_effect=lambda: events.append("settings") or Policy(),
        ) as settings,
        patch(f"{RUNNER}.input_policy", return_value=Policy()),
        patch(
            f"{RUNNER}.query_settings",
            return_value={"first_year": 2022, "last_year": 2026},
        ),
        patch(f"{RUNNER}.read_inputs") as read,
        patch(f"{RUNNER}.read_connections") as connections,
        patch(f"{RUNNER}.extract") as extract,
        patch(f"{RUNNER}.save_json"),
    ):
        read.return_value = Inputs()
        connections.return_value.__enter__.side_effect = lambda: (
            events.append("connections") or (MagicMock(), MagicMock())
        )
        extract.return_value = Snapshot()
        result = CliRunner().invoke(
            cli,
            [
                "fmi",
                "extract",
                "--inputs",
                str(inputs),
                "--output",
                str(tmp_path / "snapshot.json"),
            ],
        )
    assert result.exit_code == 0, result.output
    settings.assert_called_once()
    assert events == ["settings", "connections"]
