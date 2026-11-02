"""Dossier forecast-only Light connection; settings owned by the entry point."""

import os
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any, cast

from aily_data_access_layer.cloud_interface.aws.aws_provider import AWSCloudProvider
from aily_data_access_layer.config.database import DBConfig, EngineConfig
from aily_data_access_layer.connectors.db.db import DBConnector
from aily_data_access_layer.dal import Dal
from boto3 import Session
from botocore.config import Config

from .forecast import verify_read_only


class ProfileProvider(AWSCloudProvider):
    def get_secrets_client(self, region_name: str | None = None) -> Any:
        return self.session.client(
            "secretsmanager",
            region_name=region_name or self.region_name,
            config=Config(
                connect_timeout=10, read_timeout=20, retries={"max_attempts": 1}
            ),
        )


@contextmanager
def light_connection() -> Iterator[DBConnector]:
    profile, region = os.environ.get("AWS_PROFILE"), os.environ.get("AWS_REGION")
    if profile and not region:
        raise ValueError("Set AWS_REGION before a profiled dossier forecast query")
    if profile and os.environ.get("AILY_CLOUD_PROVIDER") != "aws":
        raise ValueError("Profiled dossier forecasts require AILY_CLOUD_PROVIDER=aws")
    provider = (
        ProfileProvider(
            region_name=cast(str, region),
            session=Session(profile_name=profile, region_name=region),
        )
        if profile
        else None
    )
    dal = Dal(
        cloud_provider=provider,
        db_config=DBConfig(
            db_user="ro",
            statement_timeout_ms=25000,
            engine_config=EngineConfig(connect_args={"connect_timeout": 10}),
            session_settings={"default_transaction_read_only": "on"},
        ),
    )
    with cast(AbstractContextManager[DBConnector], dal.db) as client:
        verify_read_only(client)
        yield client
