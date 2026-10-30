# Aily Project Starter

One small repository per project, with published Aily libraries managed by `uv`.
No FIN checkout, workspace dependencies, Docker, or deployment pipeline required.

## First Setup

Requires `uv >= 0.11.32`, Python 3.11, an Aily package entitlement, and cloud
credentials with permission for the selected tenant. You do not need a separate
Cloudsmith account if your existing FIN checkout already has an Aily entitlement.
Database access may also require VPN/network access. Installing libraries does
not grant data access.

1. Store your existing Aily entitlement for the private package index. The
   template uses Cloudsmith's Basic-auth endpoint; it does not embed a token.
   If your FIN checkout already installs Aily packages, reuse the entitlement
   token from its Cloudsmith index URL. Log in interactively so the token is
   entered at the password prompt, not saved in shell history or project files:

   ```bash
   uv auth login --username token \
     https://dl.cloudsmith.io/basic/ailylabs/pip/python/simple/
   ```

   Enter `token` as the username and your existing entitlement token as the
   password when prompted. If `uv` cannot use your OS credential store, set
   `UV_INDEX_AILY_USERNAME=token` and `UV_INDEX_AILY_PASSWORD` through your
   shell's secret manager for the duration of package installation. `uv` does
   not read project `.env` files for package installation. Never put the token
   in `pyproject.toml`, `uv.lock`, `.env`, or a command-line argument.

2. Install and configure runtime context:

   ```bash
   uv sync
   cp .env.example .env
   ```

   Fill in `.env` with your tenant, environment, AWS region and approved profile.
   Shell variables take precedence over `.env`. Runtime loads only `.env` from
   the current directory, never a parent repository's file.

3. Authenticate and check access:

   ```bash
   aws sso login --profile <your-profile>
   uv run aily-project --help
   uv run aily-project database check
   uv run aily-project database check-shared
   ```

   Use SSO only if your profile uses SSO; otherwise follow your credential flow.
   The check queries connection metadata only. It uses `db_user="ro"` plus a
   read-only session; it does not load tenant tables or write to the database.
   If the tenant lacks an `ro` secret/grant, request access rather than silently
   switching to `dbo`.

   `check-shared` separately checks DAL's cross-tenant shared database. It uses
   DAL's shared Secrets Manager credential resolution and never prints credentials.
   Your AWS identity still needs permission to retrieve the secret, and your network
   must reach the shared database. DAL defaults this connection to Aurora and the
   `dbo` credential route; the smoke check explicitly requests a read-only session.
   For a team-provided shared read-only secret, set
   `DAL_SHARED_DB_CREDENTIALS_PATH` in `.env`.

4. Commit the generated `uv.lock` after successful resolution. Use
   `uv sync --locked` on subsequent installs to detect dependency drift.
   The template intentionally starts without a lock: it must be resolved against
   your authenticated index, not copied from FIN's workspace.

## Add Only What You Need

```bash
uv add aily-fin-common
uv add aily-lightweight-time-series
uv add aily-ai-brain
uv add aily-ai-tools
uv sync --group notebook
uv sync --group ui
```

These are choices, not a bulk install command. Add one library when needed.
`aily-ai-tools` provides development utilities, not every Aily capability.
MCP servers and hosted Aily services require their own access/configuration;
they are not enabled merely by installing Python libraries.
Published finance packages may pull ML dependencies; inspect their requirements
before adding them. For GCP, use `uv add "aily-data-access-layer[gcp]"` and your
approved GCP configuration/authentication instead of AWS profiles.

Package and import names can differ: `aily-fin-common` imports as `common`.
Check each library's documentation. Avoid `workspace = true`, sibling path
dependencies, and editable FIN checkouts unless actively developing that library.

## Smoke-Test Notebook

Open `notebooks/00_smoke_test.ipynb` with the project's `.venv` kernel, or launch
Jupyter from the repo root:

```bash
uv sync --locked --group notebook
uv run --locked --group notebook jupyter notebook
```

Run all cells. Local imports, CLI and unit tests run without cloud credentials.
For tenant/shared database checks, fill `.env`, authenticate your AWS profile,
connect VPN if required, set `RUN_DATABASE_CHECKS = True`, then restart the kernel
and run all cells again. Checks verify read-only sessions and optionally locate
`social_media_bright_data_instagram_posts` via metadata; no business rows are read.
The summary distinguishes passed, failed and skipped checks. Clear all notebook
outputs before committing.

## Develop

Start business logic in `src/aily_project/services/<service>/service.py` and expose
it through a service runner registered in `cli.py`. Pass the DAL/client into
helpers; the runner owns initialization and cleanup. For scheduled batch work,
grow to `services/<service>/tasks/<task>/`, with config, runner, steps and pipeline
modules as needed. No production scaffolding is necessary for a one-off analysis.

For a small database query, inside an executable task:

```python
from contextlib import AbstractContextManager
from typing import cast

from aily_data_access_layer.config.database import DBConfig
from aily_data_access_layer.connectors.db.db import DBConnector
from aily_data_access_layer.dal import Dal
from aily_py_commons.aily_settings import AilySettings

# Run with tenant/environment already exported.
AilySettings(use_dotenv=False)
dal = Dal(
    db_config=DBConfig(
        db_user="ro",
        session_settings={"default_transaction_read_only": "on"},
    )
)
with cast(AbstractContextManager[DBConnector], dal.db) as db:
    rows = db.execute_and_fetch("SELECT current_date AS today")
```

For shared cross-tenant data, access `dal.shared_db` instead. DAL resolves its
credential separately from `dal.db`; the shared connection defaults to Aurora and
the shared `dbo` secret route. This complete entry-point example initializes
settings first, enables session-level read-only mode, verifies it, then discovers
available tables before querying a known table:

```python
from contextlib import AbstractContextManager
from typing import cast

from aily_data_access_layer.config.database import DBConfig
from aily_data_access_layer.connectors.db.db import DBConnector
from aily_data_access_layer.dal import Dal
from aily_data_access_layer.utils.db_type import DBTypes
from aily_py_commons.aily_settings import AilySettings

# Set AILY_TENANT, AILY_ENV and cloud credentials in the environment first.
AilySettings(use_dotenv=False)
dal = Dal(
    shared_db_config=DBConfig(
        db_type=DBTypes.AURORA,
        db_user="dbo",
        session_settings={"default_transaction_read_only": "on"},
    )
)
with cast(AbstractContextManager[DBConnector], dal.shared_db) as shared_db:
    status = shared_db.execute_and_fetch(
        "SELECT current_database() AS database_name, "
        "current_user AS database_user, "
        "current_setting('transaction_read_only') AS read_only"
    )[0]
    if status["read_only"] != "on":
        raise RuntimeError("Shared DB session is not read-only")

    tables = shared_db.execute_and_fetch(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
          AND table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name
        LIMIT 100
        """
    )
    # After reviewing the discovered schema, query only required columns and rows.
    # rows = shared_db.execute_and_fetch(
    #     "SELECT key_id, metric_value FROM approved_schema.approved_table "
    #     "WHERE metric_date >= %s ORDER BY metric_date DESC LIMIT 100",
    #     bind_params=(start_date,),
    # )
```

Verify `transaction_read_only` is `on` before any exploratory query. This connection
uses a `dbo` credential route by default; the session setting is a guardrail, not
a database-enforced read-only role. Do not let an agent run arbitrary SQL or
DDL/DML against shared data. Ask for a dedicated shared read-only credential when
available. DAL supports `DAL_SHARED_DB_CREDENTIALS_PATH` as an environment override;
never hardcode a secret or credential in code.

Use bind parameters for user-supplied values. Filter tenant tables by date/scope,
select only required columns, and avoid exporting sensitive data into Git.
For lakehouse work use DAL's DataLake API; for bulk transfers use DAL orchestration
instead of hand-written S3/DB clients. Add only the capabilities your task needs.

```bash
uv run pytest -m unit
uv run pytest --cov=aily_project --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

Tests need installed libraries but no AWS login, database, or tenant configuration.
Data and generated outputs belong in ignored `data/` and `outputs/` directories.
Notebooks must have outputs cleared before committing.

## Reuse For Each New Project

Publish this repo privately and mark it as a GitHub template, then choose
**Use this template** for each project. Or copy the files into a new directory
without `.git`, `.venv`, `.env`, data or outputs, and run `git init`.

Rename `[project].name` and its description for the new project. You can keep the
internal module `aily_project` and CLI `aily-project`, since each project has its
own virtualenv. If you rename them, also update entry point, imports and tests.
Resolve/commit each project's own lockfile.

To migrate an existing FIN subfolder, move its project-owned code and tests here,
list its third-party/Aily imports in pyproject.toml via `uv add`, remove path hacks,
and move runtime context into this project's ignored `.env`. Do not copy FIN's
environment, lockfile, credentials, workspace metadata or deployment workflows.
