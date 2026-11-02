"""Entry-point connection ownership; measurements still use injected readers."""

import os
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any, cast

from aily_data_access_layer.cloud_interface.aws.aws_provider import AWSCloudProvider
from aily_data_access_layer.config.database import DBConfig, EngineConfig
from aily_data_access_layer.connectors.db.db import DBConnector
from aily_data_access_layer.dal import Dal
from aily_data_access_layer.utils.db_type import DBTypes
from boto3 import Session
from botocore.config import Config

from .extraction import verify_read_only


class ProfileCloudProvider(AWSCloudProvider):
    """Keep Secrets Manager on the explicitly injected AWS profile session.

    The published provider's secrets method creates a default-chain session.
    This public-method adapter preserves profile isolation, including secrets
    whose ARN specifies a different region. DAL still resolves all credentials.
    """

    def get_secrets_client(self, region_name: str | None = None) -> Any:
        return self.session.client(
            "secretsmanager",
            region_name=region_name or self.region_name,
            config=Config(
                connect_timeout=10, read_timeout=20, retries={"max_attempts": 1}
            ),
        )


def profile_provider(profile: str | None) -> ProfileCloudProvider | None:
    """Called only after AilySettings; no cloud objects at import time."""
    if not profile:
        return None
    if os.environ.get("AILY_CLOUD_PROVIDER") != "aws":
        raise ValueError("AWS profiles require AILY_CLOUD_PROVIDER=aws")
    region = os.environ.get("AWS_REGION")
    if not region:
        raise ValueError("Set AWS_REGION before creating profiled connections")
    return ProfileCloudProvider(
        region_name=region,
        session=Session(profile_name=profile, region_name=region),
    )


@contextmanager
def read_connections() -> Iterator[tuple[DBConnector, DBConnector]]:
    """Separate DALs/profiles; verify both sessions before any source query."""
    common: dict[str, Any] = dict(
        statement_timeout_ms=25000,
        engine_config=EngineConfig(connect_args={"connect_timeout": 10}),
        session_settings={"default_transaction_read_only": "on"},
    )
    light_profile = os.environ.get("AWS_PROFILE")
    shared_profile = os.environ.get("FMI_SHARED_AWS_PROFILE") or light_profile
    light_dal = Dal(
        cloud_provider=profile_provider(light_profile),
        db_config=DBConfig(db_user="ro", **common),
    )
    shared_dal = Dal(
        cloud_provider=profile_provider(shared_profile),
        shared_db_config=DBConfig(db_type=DBTypes.AURORA, db_user="dbo", **common),
    )
    with (
        cast(AbstractContextManager[DBConnector], light_dal.db) as light,
        cast(AbstractContextManager[DBConnector], shared_dal.shared_db) as shared,
    ):
        verify_read_only(light)
        verify_read_only(shared)
        yield light, shared
