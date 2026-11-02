"""Extend the existing Click CLI; initialize settings once before config/DAL."""

import json
import os
from dataclasses import asdict
from pathlib import Path

import click
from aily_py_commons.aily_settings import AilySettings
from dotenv import load_dotenv

from .collection import collected_inputs, collection_payload, inventory
from .compact_inputs import SCHEMA as COMPACT_SCHEMA
from .compact_inputs import read_reference, refresh_reviews, write_bundle
from .configuration import document, input_policy, prepare, query_settings
from .connections import read_connections
from .data_handoff import build_handoff, query_pack
from .extraction import extract
from .handover import candidate_symbols
from .inputs import (
    as_dict,
    merge_reviews,
    propose_mappings,
    propose_post_reviews,
    read_inputs,
    seed_inputs,
)
from .models import fingerprint, truth
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


@fmi.command("check-connections")
def check_connections_task() -> None:
    """Verify both configured sessions without reading business tables."""
    initialize()
    with read_connections() as (light, shared):
        for name, client in (("light", light), ("shared", shared)):
            rows = client.fetch_data_as_df(
                "SELECT current_user AS database_role, "
                "current_setting('transaction_read_only') AS transaction_read_only, "
                "current_setting('default_transaction_read_only') "
                "AS default_transaction_read_only"
            ).to_dict("records")
            click.echo(json.dumps({"source": name, **rows[0]}))


@fmi.command("prepare-inputs")
@click.option("--raw", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--handover", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--existing", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--inventory", "inventory_path", type=click.Path(exists=True, path_type=Path)
)
@click.option("--output", type=click.Path(path_type=Path), required=True)
def prepare_inputs(
    raw: Path,
    handover: Path,
    existing: Path | None,
    inventory_path: Path | None,
    output: Path,
) -> None:
    """Create editable per-brand JSON without cloud access or report measurements."""
    if output.exists():
        raise click.ClickException(
            "Input exists; use --existing and a new --output path to preserve decisions"
        )
    data = prepare(
        raw, handover, Policy(), existing=existing, inventory_path=inventory_path
    )
    write_bundle(data, output)
    mandatory = sum(truth(b["identity"].get("fmi_required")) for b in data["brands"])
    click.echo(f"{len(data['brands'])} prospects; {mandatory} mandatory event brands")


@fmi.command("simplify-inputs")
@click.option(
    "--inputs",
    "inputs_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option("--output", type=click.Path(path_type=Path), required=True)
def simplify_inputs(inputs_path: Path, output: Path) -> None:
    """Split verbose v1 JSON into compact settings, policy and preserved reviews."""
    data = json.loads(inputs_path.read_text())
    if data.get("schema_version") != "fmi-input-v1":
        raise click.ClickException("Migration requires the verbose fmi-input-v1 JSON")
    try:
        write_bundle(data, output)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"{len(data['brands'])} brands migrated; review decisions preserved")


@fmi.command("align-dossiers")
@click.option(
    "--inputs",
    "inputs_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option("--handover", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--roadmap", type=click.Path(exists=True, path_type=Path))
@click.option("--output", type=click.Path(path_type=Path), required=True)
def align_dossier_task(
    inputs_path: Path, handover: Path, roadmap: Path | None, output: Path
) -> None:
    """Seed editable business parameters once, without importing measurements."""
    from .compact_inputs import materialize
    from .dossier_inputs import align_dossiers

    if output.exists():
        raise click.ClickException(
            "Choose a new output path; existing inputs are never overwritten"
        )
    data, audit = align_dossiers(json.loads(inputs_path.read_text()), handover, roadmap)
    materialize(data)
    save_json(data, output)
    linked = sum(bool(r.get("source")) for r in audit)
    click.echo(
        f"{len(audit)} prospects preserved; "
        f"{linked} linked to dossier business parameters"
    )


@fmi.command("refresh-reviews")
@click.option(
    "--inputs",
    "inputs_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option("--output", type=click.Path(path_type=Path), required=True)
def refresh_review_task(inputs_path: Path, output: Path) -> None:
    """Preserve choices in a new review file; changed settings reset approvals."""
    data = json.loads(inputs_path.read_text())
    if data.get("schema_version") != COMPACT_SCHEMA:
        raise click.ClickException("Use compact fmi-input-v2 inputs")
    try:
        stale = refresh_reviews(inputs_path, data, output)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(
        f"Saved review proposal; {len(stale)} changed analyses require review. "
        f"Set review_file to {output.name} after reviewing it."
    )


def calculation_policy(inputs_path: Path, snapshot_path: Path, offline: bool) -> Policy:
    if offline:
        snapshot = read_snapshot(snapshot_path)
        recorded = snapshot.metadata.get("resolved_policy")
        if not recorded:
            raise click.ClickException(
                "Offline replay requires a recorded resolved policy"
            )
        defaults = Policy.model_validate(recorded)
    else:
        defaults = initialize()
    return input_policy(inputs_path, defaults)


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
    with read_connections() as (light, shared):
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
    policy = input_policy(inputs_path, initialize())
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
    with read_connections() as (light, shared):
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
    if inputs_path.suffix.lower() == ".json":
        original = json.loads(inputs_path.read_text())
        if original["schema_version"] == COMPACT_SCHEMA:
            review = (
                json.loads(
                    read_reference(inputs_path, original["review_file"]).read_text()
                )
                if original.get("review_file")
                else {}
            )
            sources = review.get("evidence", {}).get("source_files", [])
        else:
            sources = original.get("source_files", [])
        refreshed = document(inputs, policy, reports=reports, sources=sources)
        refreshed["query"] = original["query"]
        write_bundle(refreshed, output_dir / "FMI_inputs.json")
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
@click.option("--first-year", type=int)
@click.option("--last-year", type=int)
@click.option("--limit", type=int)
def extraction(
    inputs_path: Path,
    output: Path,
    first_year: int | None,
    last_year: int | None,
    limit: int | None,
) -> None:
    """Read Light and shared scanner; never writes database data."""
    policy = input_policy(inputs_path, initialize())
    configured = query_settings(inputs_path)
    first_year = first_year if first_year is not None else configured.get("first_year")
    last_year = last_year if last_year is not None else configured.get("last_year")
    limit = limit if limit is not None else configured.get("row_limit", 100000)
    if first_year is None or last_year is None:
        raise click.ClickException(
            "Specify query years in JSON or --first-year/--last-year"
        )
    inputs = read_inputs(inputs_path)
    with read_connections() as (light, shared):
        snapshot = extract(
            light,
            shared,
            inputs,
            first_year,
            last_year,
            limit,
            candidate_symbols=tuple(
                sorted({s for e in inputs.entities for s in candidate_symbols(e)})
            ),
        )
    snapshot.metadata["resolved_policy"] = policy.model_dump()
    snapshot.metadata["input_hash"] = fingerprint(as_dict(inputs))
    snapshot.metadata["connection_context"] = {
        "tenant": os.environ.get("AILY_TENANT"),
        "environment": os.environ.get("AILY_ENV"),
        "cloud_provider": os.environ.get("AILY_CLOUD_PROVIDER"),
        "light_aws_profile": os.environ.get("AWS_PROFILE"),
        "shared_aws_profile": os.environ.get("FMI_SHARED_AWS_PROFILE")
        or os.environ.get("AWS_PROFILE"),
    }
    save_json(asdict(snapshot), output)
    click.echo(
        f"Extracted {len(snapshot.financials)} financial candidates "
        f"and {len(snapshot.posts)} social captures; approvals unchanged"
    )


@fmi.command("data-handoff")
@click.option(
    "--inputs",
    "inputs_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option("--snapshot", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--output", type=click.Path(path_type=Path), required=True)
def data_handoff_task(inputs_path: Path, snapshot: Path, output: Path) -> None:
    """Create a shareable Markdown/SQL audit; no cloud writes or delivery refresh."""
    source = read_snapshot(snapshot)
    policy = calculation_policy(inputs_path, snapshot, offline=True)
    sql = query_pack(source)
    report, records = build_handoff(read_inputs(inputs_path), source, policy)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report)
    output.with_suffix(".sql").write_text(sql)
    save_json(records, snapshot.parent / "data-handoff-results.json")
    click.echo(f"Audited {len(records['results'])} prospects: {output}")


@fmi.command("score")
@click.option(
    "--inputs",
    "inputs_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option("--snapshot", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--output", type=click.Path(path_type=Path), required=True)
@click.option(
    "--offline",
    is_flag=True,
    help="Replay authenticated snapshot and its recorded policy; no cloud settings.",
)
def score(inputs_path: Path, snapshot: Path, output: Path, offline: bool) -> None:
    """Calculate raw reviewed scores without cohort rescaling or forecasts."""
    result = score_task(
        inputs_path,
        snapshot,
        output,
        calculation_policy(inputs_path, snapshot, offline),
    )
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
@click.option(
    "--offline",
    is_flag=True,
    help="Replay saved authenticated data; does not perform a fresh query.",
)
@click.option("--historical", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--work-dir",
    type=click.Path(path_type=Path),
    default=".work/fmi",
    show_default=True,
    help="Internal extracts/audit folder, separate from shareable output.",
)
def delivery(
    inputs_path: Path,
    snapshot: Path,
    output: Path,
    previews: bool,
    offline: bool,
    historical: Path | None,
    work_dir: Path,
) -> None:
    """Refresh from reviewed inputs, rescale, uplift and export Excel/app JSON."""
    counts = delivery_task(
        inputs_path,
        snapshot,
        output,
        calculation_policy(inputs_path, snapshot, offline),
        previews=previews,
        historical=historical,
        work_dir=work_dir,
    )
    click.echo(str(counts))
