from unittest.mock import MagicMock, patch

import pytest
from aily_data_access_layer.utils.db_type import DBTypes
from click.testing import CliRunner

from aily_project.cli import cli
from aily_project.services.database.service import (
    check_connection,
    check_shared_connection,
)

pytestmark = pytest.mark.unit
RUNNER = "aily_project.services.database.runner"


def test_cli_help_does_not_initialize_cloud() -> None:
    with patch(f"{RUNNER}.AilySettings") as settings, patch(f"{RUNNER}.Dal") as dal:
        result = CliRunner().invoke(cli, ["--help"])
        database_help = CliRunner().invoke(cli, ["database", "--help"])

    assert result.exit_code == 0
    assert "database" in result.output
    assert database_help.exit_code == 0
    assert "check-shared" in database_help.output
    settings.assert_not_called()
    dal.assert_not_called()


@pytest.mark.parametrize("command", ["check", "check-shared"])
def test_check_missing_environment_fails_before_cloud(command: str) -> None:
    with (
        patch.dict("os.environ", {}, clear=True),
        patch(f"{RUNNER}.load_dotenv"),
        patch(f"{RUNNER}.AilySettings") as settings,
        patch(f"{RUNNER}.Dal") as dal,
    ):
        result = CliRunner().invoke(cli, ["database", command])

    assert result.exit_code == 1
    assert "AILY_TENANT" in result.output
    settings.assert_not_called()
    dal.assert_not_called()


def test_check_initializes_settings_before_read_only_dal() -> None:
    events: list[str] = []
    env = {
        "AILY_TENANT": "test",
        "AILY_ENV": "dev",
        "AILY_CLOUD_PROVIDER": "aws",
    }
    with (
        patch.dict("os.environ", env, clear=True),
        patch(f"{RUNNER}.load_dotenv") as dotenv,
        patch(
            f"{RUNNER}.AilySettings",
            side_effect=lambda **kwargs: events.append("settings"),
        ) as settings,
        patch(
            f"{RUNNER}.Dal", side_effect=lambda **kwargs: events.append("dal")
        ) as dal,
        patch(f"{RUNNER}.check_connection", return_value={"read_only": "on"}),
    ):
        result = CliRunner().invoke(cli, ["database", "check"])

    assert result.exit_code == 0, result.output
    assert events == ["settings", "dal"]
    settings.assert_called_once_with(use_dotenv=False)
    assert dotenv.call_args.kwargs["override"] is False
    config = dal.call_args.kwargs["db_config"]
    assert config.db_user == "ro"
    assert config.session_settings == {"default_transaction_read_only": "on"}


def test_check_connection_closes_connector_after_success() -> None:
    dal = MagicMock()
    db = dal.db.__enter__.return_value
    db.execute_and_fetch.return_value = [{"database_name": "test"}]

    assert check_connection(dal) == {"database_name": "test"}
    dal.db.__exit__.assert_called_once_with(None, None, None)


def test_check_connection_closes_connector_after_failure() -> None:
    dal = MagicMock()
    dal.db.__enter__.return_value.execute_and_fetch.side_effect = RuntimeError("db")

    with pytest.raises(RuntimeError, match="db"):
        check_connection(dal)

    dal.db.__exit__.assert_called_once()


def test_check_shared_connection_uses_shared_connector() -> None:
    dal = MagicMock()
    db = dal.shared_db.__enter__.return_value
    db.execute_and_fetch.return_value = [{"database_name": "shared"}]

    assert check_shared_connection(dal) == {"database_name": "shared"}
    dal.shared_db.__enter__.assert_called_once()
    dal.shared_db.__exit__.assert_called_once_with(None, None, None)
    dal.db.__enter__.assert_not_called()


def test_check_shared_connection_closes_connector_after_failure() -> None:
    dal = MagicMock()
    db = dal.shared_db.__enter__.return_value
    db.execute_and_fetch.side_effect = RuntimeError("shared db")

    with pytest.raises(RuntimeError, match="shared db"):
        check_shared_connection(dal)

    dal.shared_db.__exit__.assert_called_once()
    dal.db.__enter__.assert_not_called()


def test_check_shared_initializes_read_only_shared_database() -> None:
    events: list[str] = []
    env = {
        "AILY_TENANT": "test",
        "AILY_ENV": "dev",
        "AILY_CLOUD_PROVIDER": "aws",
    }
    with (
        patch.dict("os.environ", env, clear=True),
        patch(f"{RUNNER}.load_dotenv"),
        patch(
            f"{RUNNER}.AilySettings",
            side_effect=lambda **kwargs: events.append("settings"),
        ) as settings,
        patch(
            f"{RUNNER}.Dal", side_effect=lambda **kwargs: events.append("dal")
        ) as dal,
        patch(
            f"{RUNNER}.check_shared_connection",
            return_value={"read_only": "on"},
        ),
    ):
        result = CliRunner().invoke(cli, ["database", "check-shared"])

    assert result.exit_code == 0, result.output
    assert events == ["settings", "dal"]
    settings.assert_called_once_with(use_dotenv=False)
    config = dal.call_args.kwargs["shared_db_config"]
    assert config.db_type == DBTypes.AURORA
    assert config.db_user == "dbo"
    assert config.session_settings == {"default_transaction_read_only": "on"}


@pytest.mark.parametrize("status", [{"read_only": "off"}, {}])
def test_check_shared_fails_if_session_is_not_read_only(
    status: dict[str, str],
) -> None:
    env = {
        "AILY_TENANT": "test",
        "AILY_ENV": "dev",
        "AILY_CLOUD_PROVIDER": "aws",
    }
    with (
        patch.dict("os.environ", env, clear=True),
        patch(f"{RUNNER}.load_dotenv"),
        patch(f"{RUNNER}.AilySettings"),
        patch(f"{RUNNER}.Dal"),
        patch(
            f"{RUNNER}.check_shared_connection",
            return_value=status,
        ),
    ):
        result = CliRunner().invoke(cli, ["database", "check-shared"])

    assert result.exit_code == 1
    assert "not read-only" in result.output
