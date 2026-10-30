"""Extend the existing Click CLI; initialize settings once before config/DAL."""

import json
import os
from contextlib import AbstractContextManager
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import click
from aily_data_access_layer.config.database import DBConfig, EngineConfig
from aily_data_access_layer.connectors.db.db import DBConnector
from aily_data_access_layer.dal import Dal
from aily_data_access_layer.utils.db_type import DBTypes
from aily_py_commons.aily_settings import AilySettings
from dotenv import load_dotenv

from .collection import collected_inputs, collection_payload, inventory
from .extraction import extract
from .handover import candidate_symbols
from .inputs import (
    merge_reviews,
    propose_mappings,
    propose_post_reviews,
    read_inputs,
    seed_inputs,
)
from .policy import Policy, resolve_policy
from .tasks.pipeline import delivery_task, read_snapshot, save_json, score_task
from .workbooks import input_payload, write_workbook


def initialize() -> Policy:
    load_dotenv(Path.cwd() / ".env", override=False)
    missing = [
        k
        for k in ("AILY_TENANT", "AILY_ENV", "AILY_CLOUD_PROVIDER")
        if not os.environ.get(k)
    ]
    if missing:
        raise click.ClickException("Set required variables: " + ", ".join(missing))
    AilySettings(use_dotenv=False, verbose=False)
    return resolve_policy(Path(__file__).parents[2])


@click.group()
def fmi() -> None:
    """Controlled FMI extraction, review, score and app-ready Excel."""


@fmi.command("inventory")
@click.option("--output", type=click.Path(path_type=Path), required=True)
@click.option("--inputs", "inputs_path", type=click.Path(exists=True, path_type=Path))
@click.option("--first-year", type=int, required=True)
@click.option("--last-year", type=int, required=True)
def inventory_task(
    output: Path, inputs_path: Path | None, first_year: int, last_year: int
) -> None:
    """Discover account/identity coverage without requiring score approvals."""
    initialize()
    common: dict[str, Any] = dict(
        statement_timeout_ms=25000,
        engine_config=EngineConfig(connect_args={"connect_timeout": 10}),
        session_settings={"default_transaction_read_only": "on"},
    )
    dal = Dal(
        db_config=DBConfig(db_user="ro", **common),
        shared_db_config=DBConfig(db_type=DBTypes.AURORA, db_user="dbo", **common),
    )
    with (
        cast(AbstractContextManager[DBConnector], dal.db) as light,
        cast(AbstractContextManager[DBConnector], dal.shared_db) as shared,
    ):
        result = inventory(
            light,
            shared,
            first_year,
            last_year,
            read_inputs(inputs_path) if inputs_path else None,
        )
    save_json(result, output)
    click.echo(
        f"Inventoried {len(result['registry'])} companies and "
        f"{len(result['accounts'])} account-source identifiers"
    )


@fmi.command("collect")
@click.option(
    "--inputs",
    "inputs_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option(
    "--inventory",
    "inventory_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option("--handover", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--output-dir", type=click.Path(path_type=Path), required=True)
@click.option("--first-year", type=int, required=True)
@click.option("--last-year", type=int, required=True)
@click.option("--limit", type=int, default=500000)
@click.option("--previews", is_flag=True)
def collect_task(
    inputs_path: Path,
    inventory_path: Path,
    handover: Path,
    output_dir: Path,
    first_year: int,
    last_year: int,
    limit: int,
    previews: bool,
) -> None:
    """Collect all prospect source candidates; approval is not a download gate."""
    policy = initialize()
    if any(
        (output_dir / f).exists()
        for f in ("snapshot.json", "FMI_inputs.xlsx", "FMI_collected_data.xlsx")
    ):
        raise click.ClickException(
            "Collection outputs already exist; choose a fresh output directory"
        )
    data = json.loads(inventory_path.read_text())
    if data.get("authenticated") is not True or not data.get("extracted_at"):
        raise click.ClickException(
            "Inventory must come from authenticated database discovery"
        )
    inputs, reports, audit = collected_inputs(read_inputs(inputs_path), data, handover)
    symbols = tuple(sorted({s for e in inputs.entities for s in candidate_symbols(e)}))
    handles = tuple(sorted({h for a in audit for h in a["candidate_handles"]}))
    common: dict[str, Any] = dict(
        statement_timeout_ms=25000,
        engine_config=EngineConfig(connect_args={"connect_timeout": 10}),
        session_settings={"default_transaction_read_only": "on"},
    )
    dal = Dal(
        db_config=DBConfig(db_user="ro", **common),
        shared_db_config=DBConfig(db_type=DBTypes.AURORA, db_user="dbo", **common),
    )
    with (
        cast(AbstractContextManager[DBConnector], dal.db) as light,
        cast(AbstractContextManager[DBConnector], dal.shared_db) as shared,
    ):
        snapshot = extract(
            light,
            shared,
            inputs,
            first_year,
            last_year,
            limit,
            candidate_symbols=symbols,
            candidate_handles=handles,
        )
    snapshot.metadata["resolved_policy"] = policy.model_dump()
    snapshot.metadata["candidate_search_symbols"] = list(symbols)
    snapshot.metadata["candidate_search_handles"] = list(handles)
    snapshot.metadata["inventory_queries"] = data["queries"]
    inputs = propose_post_reviews(propose_mappings(inputs, snapshot), snapshot)
    payload = collection_payload(inputs, snapshot, audit, reports)
    output_dir.mkdir(parents=True, exist_ok=True)
    save_json(asdict(snapshot), output_dir / "snapshot.json")
    save_json(reports, output_dir / "handover-index.json")
    save_json(audit, output_dir / "mapping-audit.json")
    coverage = payload["sheets"][0]["rows"]
    summary = {
        "prospects": len(coverage),
        "reports_read": len(reports),
        "financial_metric_candidates": len(snapshot.financials),
        "social_capture_rows": len(snapshot.posts),
        "prospects_with_revenue": sum(r["actual_revenue_rows"] > 0 for r in coverage),
        "prospects_with_instagram": sum(r["social_capture_rows"] > 0 for r in coverage),
        "prospects_with_both": sum(
            r["actual_revenue_rows"] > 0 and r["social_capture_rows"] > 0
            for r in coverage
        ),
        "rows": coverage,
    }
    save_json(summary, output_dir / "collection-coverage.json")
    write_workbook(
        input_payload(inputs), output_dir / "FMI_inputs.xlsx", previews=previews
    )
    write_workbook(payload, output_dir / "FMI_collected_data.xlsx", previews=previews)
    click.echo(str({k: v for k, v in summary.items() if k != "rows"}))


@fmi.command("collection-export")
@click.option(
    "--inputs",
    "inputs_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option("--snapshot", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--audit", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--reports", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--output", type=click.Path(path_type=Path), required=True)
@click.option("--previews", is_flag=True)
def collection_export(
    inputs_path: Path,
    snapshot: Path,
    audit: Path,
    reports: Path,
    output: Path,
    previews: bool,
) -> None:
    """Re-export collected sources without repeating database queries."""
    payload = collection_payload(
        read_inputs(inputs_path),
        read_snapshot(snapshot),
        json.loads(audit.read_text()),
        json.loads(reports.read_text()),
    )
    write_workbook(payload, output, previews=previews)


@fmi.command("seed")
@click.option(
    "--prospects", type=click.Path(exists=True, path_type=Path), required=True
)
@click.option("--legacy", type=click.Path(exists=True, path_type=Path))
@click.option("--output", type=click.Path(path_type=Path), required=True)
@click.option("--previews", is_flag=True)
def seed(prospects: Path, legacy: Path | None, output: Path, previews: bool) -> None:
    """Create inputs or preserve existing review rows during an explicit refresh."""
    inputs = seed_inputs(prospects, legacy)
    if output.exists():
        inputs = merge_reviews(inputs, read_inputs(output))
        # Recoverable backup before refreshing a human-managed workbook.
        backup = output.with_suffix(".xlsx.bak")
        if backup.exists():
            raise click.ClickException(
                "Existing backup: move it before refreshing inputs"
            )
        backup.write_bytes(output.read_bytes())
    write_workbook(input_payload(inputs), output, previews=previews)
    click.echo(
        f"Inputs created; "
        f"{sum(bool(e.get('prospect')) for e in inputs.entities)} prospects"
    )


@fmi.command("extract")
@click.option(
    "--inputs",
    "inputs_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option("--output", type=click.Path(path_type=Path), required=True)
@click.option("--first-year", type=int, required=True)
@click.option("--last-year", type=int, required=True)
@click.option("--limit", type=int, default=100000)
def extraction(
    inputs_path: Path, output: Path, first_year: int, last_year: int, limit: int
) -> None:
    """Read Light and shared scanner; never writes database data."""
    policy = initialize()
    inputs = read_inputs(inputs_path)
    common: dict[str, Any] = dict(
        statement_timeout_ms=25000,
        engine_config=EngineConfig(connect_args={"connect_timeout": 10}),
        session_settings={"default_transaction_read_only": "on"},
    )
    dal = Dal(
        db_config=DBConfig(db_user="ro", **common),
        shared_db_config=DBConfig(db_type=DBTypes.AURORA, db_user="dbo", **common),
    )
    with (
        cast(AbstractContextManager[DBConnector], dal.db) as light,
        cast(AbstractContextManager[DBConnector], dal.shared_db) as shared,
    ):
        snapshot = extract(light, shared, inputs, first_year, last_year, limit)
    snapshot.metadata["resolved_policy"] = policy.model_dump()
    save_json(asdict(snapshot), output)
    click.echo(
        f"Extracted {len(snapshot.financials)} financial candidates "
        f"and {len(snapshot.posts)} social captures; approvals unchanged"
    )


@fmi.command("score")
@click.option(
    "--inputs",
    "inputs_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option("--snapshot", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--output", type=click.Path(path_type=Path), required=True)
def score(inputs_path: Path, snapshot: Path, output: Path) -> None:
    """Calculate raw reviewed scores without cohort rescaling or forecasts."""
    result = score_task(inputs_path, snapshot, output, initialize())
    click.echo(f"Raw results: {len(result['results'])} prospects")


@fmi.command("propose-mappings")
@click.option(
    "--inputs",
    "inputs_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option("--snapshot", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--output", type=click.Path(path_type=Path), required=True)
@click.option("--previews", is_flag=True)
def proposals(inputs_path: Path, snapshot: Path, output: Path, previews: bool) -> None:
    """Write proposals to a new workbook; original inputs are preserved."""
    if output.exists():
        raise click.ClickException("Proposal output exists; choose a new path")
    data = read_snapshot(snapshot)
    inputs = propose_post_reviews(
        propose_mappings(read_inputs(inputs_path), data), data
    )
    write_workbook(input_payload(inputs), output, previews=previews)


@fmi.command("deliver")
@click.option(
    "--inputs",
    "inputs_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option("--snapshot", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--output", type=click.Path(path_type=Path), required=True)
@click.option("--previews", is_flag=True)
def delivery(inputs_path: Path, snapshot: Path, output: Path, previews: bool) -> None:
    """Refresh from reviewed inputs, rescale, uplift and export Excel/app JSON."""
    counts = delivery_task(
        inputs_path, snapshot, output, initialize(), previews=previews
    )
    click.echo(str(counts))
