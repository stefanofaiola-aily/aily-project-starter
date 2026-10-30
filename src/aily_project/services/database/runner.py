"""Own settings and DAL lifecycle at the executable boundary."""

import json
import os
from pathlib import Path

import click
from aily_data_access_layer.config.database import DBConfig
from aily_data_access_layer.dal import Dal
from aily_data_access_layer.utils.db_type import DBTypes
from aily_py_commons.aily_settings import AilySettings
from dotenv import load_dotenv

from aily_project.services.database.service import (
    check_connection,
    check_shared_connection,
)


@click.group()
def database() -> None:
    """Database tools. Uses the tenant/environment in your .env or shell."""


@database.command("check")
def check() -> None:
    """Verify cloud credentials and a read-only database connection."""
    # An explicit file avoids accidentally loading a parent FIN repo's .env.
    load_dotenv(Path.cwd() / ".env", override=False)
    required = ("AILY_TENANT", "AILY_ENV", "AILY_CLOUD_PROVIDER")
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        raise click.ClickException(f"Set required variables: {', '.join(missing)}")

    AilySettings(use_dotenv=False)
    dal = Dal(
        db_config=DBConfig(
            db_user="ro",
            session_settings={"default_transaction_read_only": "on"},
        )
    )
    click.echo(json.dumps(check_connection(dal), indent=2, default=str))


@database.command("check-shared")
def check_shared() -> None:
    """Check read-only session access to DAL's shared database."""
    load_dotenv(Path.cwd() / ".env", override=False)
    required = ("AILY_TENANT", "AILY_ENV", "AILY_CLOUD_PROVIDER")
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        raise click.ClickException(f"Set required variables: {', '.join(missing)}")

    AilySettings(use_dotenv=False)
    dal = Dal(
        shared_db_config=DBConfig(
            db_type=DBTypes.AURORA,
            db_user="dbo",
            session_settings={"default_transaction_read_only": "on"},
        )
    )
    connection_info = check_shared_connection(dal)
    if str(connection_info.get("read_only", "")).lower() != "on":
        raise click.ClickException(
            "Shared database session is not read-only; refusing to continue."
        )
    click.echo(json.dumps(connection_info, indent=2, default=str))
