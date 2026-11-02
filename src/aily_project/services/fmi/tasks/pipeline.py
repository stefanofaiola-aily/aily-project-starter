"""File orchestration. Cloud/database ownership remains at the CLI boundary."""

import json
from dataclasses import asdict
from pathlib import Path

import yaml

from ..flat_delivery import flat_payload
from ..inputs import as_dict, read_inputs
from ..models import Inputs, Row, Snapshot, clean, fingerprint
from ..policy import Policy
from ..run_records import (
    historical_comparison,
    monthly_context,
    output_dictionary,
    write_brand_records,
)
from ..scoring import build_raw, calculate
from ..workbooks import delivery_payload, write_workbook


def save_json(value: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(clean(value), indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    )


def read_snapshot(path: Path) -> Snapshot:
    data = json.loads(path.read_text())
    result = Snapshot(**data)
    if result.metadata.get("authenticated") is not True or not result.metadata.get(
        "extracted_at"
    ):
        raise ValueError("Use an authenticated DB export with extraction provenance")
    return result


def score_task(
    inputs_path: Path, snapshot_path: Path, output: Path, policy: Policy
) -> Row:
    inputs, snapshot = read_inputs(inputs_path), read_snapshot(snapshot_path)
    run_id = fingerprint(
        {
            "inputs": as_dict(inputs),
            "snapshot": asdict(snapshot),
            "policy": policy.model_dump(),
        }
    )
    results, _ = build_raw(inputs, snapshot, policy, run_id)
    record = {
        "run_id": run_id,
        "policy": policy.model_dump(),
        "results": [asdict(r) for r in results],
        "input_hash": fingerprint(as_dict(inputs)),
        "snapshot_hash": fingerprint(asdict(snapshot)),
    }
    save_json(
        {"inputs": as_dict(inputs), "policy": policy.model_dump()},
        output.with_name("resolved-inputs.json"),
    )
    save_json(record, output)
    return record


def delivery_task(
    inputs_path: Path,
    snapshot_path: Path,
    output: Path,
    policy: Policy,
    *,
    previews: bool = False,
    historical: Path | None = None,
    work_dir: Path | None = None,
) -> Row:
    inputs, snapshot = read_inputs(inputs_path), read_snapshot(snapshot_path)
    counts = deliver(
        inputs,
        snapshot,
        output,
        policy,
        previews=previews,
        historical=historical,
        work_dir=work_dir,
    )
    event_file = inputs_path.parent / "raw" / "FMI index companies(Sheet1).csv"
    audit = {}
    if event_file.is_file():
        from ..configuration import event_reconciliation

        rows = json.loads(output.with_suffix(".json").read_text())
        audit = event_reconciliation(event_file, inputs, rows)
        work = work_dir or output.parent / ".work"
        coverage_rows = json.loads((work / "delivery-audit.json").read_text())[
            "prospect_coverage"
        ]
        covered_ids = {r["brand_id"] for r in coverage_rows}
        audit["reconciliation_scope"] = "filtered_delivery_and_full_internal_coverage"
        audit["missing_calculation_results"] = [
            r["brand_id"] for r in audit["brands"] if r["brand_id"] not in covered_ids
        ]
        audit["uncovered_fmi_count"] = len(audit["missing_delivery"])
        audit["uncovered_forecast_count"] = sum(
            r.get("forecast_status") != "available"
            for r in coverage_rows
            if r["brand_id"] in {b["brand_id"] for b in audit["brands"]}
        )
        save_json(audit, work / "dinner-reconciliation.json")
        if any(
            audit[k]
            for k in (
                "missing_inputs",
                "missing_calculation_results",
                "not_mandatory",
                "invitation_mismatch",
            )
        ):
            raise ValueError("Dinner coverage mismatch; see dinner-reconciliation.json")
    from ..release_note import official_run_note

    work = work_dir or output.parent / ".work"
    (output.parent / "OFFICIAL_RUN.md").write_text(
        official_run_note(
            json.loads((work / "delivery-audit.json").read_text()),
            audit,
            [],
        )
    )
    return counts


def deliver(
    inputs: Inputs,
    snapshot: Snapshot,
    output: Path,
    policy: Policy,
    *,
    previews: bool = False,
    historical: Path | None = None,
    work_dir: Path | None = None,
) -> Row:
    work = work_dir or output.parent / ".work"
    if work.resolve() == output.parent.resolve():
        raise ValueError("Work directory must be separate from delivery directory")
    work.mkdir(parents=True, exist_ok=True)
    run_id = fingerprint(
        {
            "inputs": as_dict(inputs),
            "snapshot": asdict(snapshot),
            "policy": policy.model_dump(),
        }
    )
    results, cohort = calculate(inputs, snapshot, policy, run_id)
    records = delivery_payload(results, snapshot, policy, cohort)
    save_json(
        {"inputs": as_dict(inputs), "policy": policy.model_dump()},
        work / "resolved-inputs.json",
    )
    contexts = monthly_context(inputs, snapshot)
    comparisons = historical_comparison(results, historical)
    flat = flat_payload(results, inputs, snapshot, contexts)
    fields = output_dictionary(flat["sheets"])
    # Keep every prospect's coverage internally; the manager/app receives only
    # computable selected FMI headlines. A missing forecast does not erase FMI.
    coverage_rows = flat["sheets"][0]["rows"]
    flat["sheets"][0]["rows"] = [
        r
        for r in coverage_rows
        if r.get("fmi_status") == "available"
        and r.get("raw_fmi") is not None
        and r.get("display_fmi") is not None
    ]
    write_workbook(flat, output, previews=previews, work_dir=work)
    # A simple app array and one Excel table project exactly the same service rows.
    save_json(flat["sheets"][0]["rows"], output.with_suffix(".json"))
    # Different-grain audit detail stays local, outside the shareable delivery.
    save_json(
        {
            "contract_version": "fmi-flat-v3",
            "run_id": run_id,
            "cohort": cohort,
            "policy": policy.model_dump(),
            "source_extracted_at": snapshot.metadata["extracted_at"],
            "input_hash": fingerprint(as_dict(inputs)),
            "snapshot_hash": fingerprint(asdict(snapshot)),
            "delivery_filter": "available_fmi_with_raw_and_display_scores",
            "prospect_coverage": coverage_rows,
            "supporting": {
                s["name"]: s["rows"]
                for s in records["sheets"][1:]
                if s["name"] != "Fields"
            },
            "social_monthly_context": contexts,
            "historical_comparison": comparisons,
            "context_notice": "Financial candidates and social context are NOT "
            "eligible historical app metrics. Use Delivery statuses to release scores.",
        },
        work / "delivery-audit.json",
    )
    (work / "resolved-policy.yaml").write_text(
        yaml.safe_dump(policy.model_dump(), sort_keys=True)
    )
    counts = {
        "prospects": len(results),
        "exported_prospects": len(flat["sheets"][0]["rows"]),
        "excluded_prospects": len(coverage_rows) - len(flat["sheets"][0]["rows"]),
        "available_fmi": sum(
            r.values.get("fmi_status") == "available" for r in results
        ),
        "available_forecast": sum(
            r.values.get("forecast_status") == "available" for r in results
        ),
        "prospects_with_revenue_candidates": sum(
            bool(r.get("actual_revenue_candidate_count")) for r in coverage_rows
        ),
        "prospects_with_instagram_captures": sum(
            bool(r.get("social_capture_count")) for r in coverage_rows
        ),
        "prospects_with_target_end_forecast_candidates": sum(
            bool(r.get("observed_target_forecast_candidate_count"))
            for r in coverage_rows
        ),
    }
    save_json(
        {
            **counts,
            "completion_status": "complete"
            if counts["available_fmi"] == counts["available_forecast"] == len(results)
            else "incomplete",
            "source_extracted_at": snapshot.metadata["extracted_at"],
            "queries": snapshot.metadata.get("queries", []),
            "source_limitations": snapshot.metadata.get("limitations", []),
            "financial_observations_with_verified_availability": sum(
                bool(r.get("vintage_verified")) and bool(r.get("available_at"))
                for r in snapshot.financials
            ),
            "run_id": run_id,
            "input_hash": fingerprint(as_dict(inputs)),
            "snapshot_hash": fingerprint(asdict(snapshot)),
            "policy_hash": fingerprint(policy.model_dump()),
            "gaps": [
                {
                    "brand_id": r.brand_id,
                    "missing_reasons": r.record()["missing_reasons"],
                    "forecast_missing_reason": r.values.get("forecast_missing_reason"),
                }
                for r in results
            ],
        },
        work / "coverage.json",
    )
    save_json(fields, work / "output-dictionary.json")
    write_brand_records(
        inputs,
        snapshot,
        results,
        policy,
        work / "brand-runs" / run_id[:12],
        contexts=contexts,
        comparisons=comparisons,
    )
    return counts
