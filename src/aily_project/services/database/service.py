"""Database operations with injected DAL clients."""

from contextlib import AbstractContextManager
from typing import cast

from aily_data_access_layer.connectors.db.db import DBConnector
from aily_data_access_layer.dal import Dal

CONNECTION_QUERY = """
SELECT current_database() AS database_name,
       current_user AS database_user,
       current_setting('transaction_read_only') AS read_only
"""


def check_connection(dal: Dal) -> dict[str, object]:
    """Check connection metadata without reading tenant business data."""
    return _check_connector(dal.db)


def check_shared_connection(dal: Dal) -> dict[str, object]:
    """Check shared database metadata without reading business data."""
    return _check_connector(dal.shared_db)


def _check_connector(connector: DBConnector) -> dict[str, object]:
    # DAL's runtime context manager works; its __exit__ annotations are too narrow.
    with cast(AbstractContextManager[DBConnector], connector) as db:
        rows = db.execute_and_fetch(CONNECTION_QUERY)
    return dict(rows[0])
