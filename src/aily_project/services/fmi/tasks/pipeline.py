"""File orchestration. Cloud/database ownership remains at the CLI boundary."""

import json
from dataclasses import asdict
from pathlib import Path

import yaml

from ..inputs import as_dict, read_inputs
from ..models import Inputs, Row, Snapshot, clean, fingerprint
from ..policy import Policy
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
    save_json(record, output)
    return record


def delivery_task(
    inputs_path: Path,
    snapshot_path: Path,
    output: Path,
    policy: Policy,
    *,
    previews: bool = False,
) -> Row:
    inputs, snapshot = read_inputs(inputs_path), read_snapshot(snapshot_path)
    return deliver(inputs, snapshot, output, policy, previews=previews)


def deliver(
    inputs: Inputs,
    snapshot: Snapshot,
    output: Path,
    policy: Policy,
    *,
    previews: bool = False,
) -> Row:
    run_id = fingerprint(
        {
            "inputs": as_dict(inputs),
            "snapshot": asdict(snapshot),
            "policy": policy.model_dump(),
        }
    )
    results, cohort = calculate(inputs, snapshot, policy, run_id)
    records = delivery_payload(results, snapshot, policy, cohort)
    write_workbook(records, output, previews=previews)
    # Workbook and app JSON are projections of exactly these result objects.
    save_json(
        {
            "contract_version": "fmi-app-v1",
            "run_id": run_id,
            "delivery": records["sheets"][0]["rows"],
            "cohort": cohort,
        },
        output.with_suffix(".json"),
    )
    output.with_name("resolved-policy.yaml").write_text(
        yaml.safe_dump(policy.model_dump(), sort_keys=True)
    )
    counts = {
        "prospects": len(results),
        "available_fmi": sum(
            r.values.get("fmi_status") == "available" for r in results
        ),
        "available_forecast": sum(
            r.values.get("forecast_status") == "available" for r in results
        ),
    }
    save_json(
        {
            **counts,
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
        output.with_name("coverage.json"),
    )
    return counts
