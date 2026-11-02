"""Workbook payloads use the same canonical result objects as the app export."""

import json
import os
import subprocess
import tempfile
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from .contract import FIELDS, canonical_record
from .inputs import SHEETS
from .models import FMIResult, Inputs, Row, Snapshot, clean, fingerprint
from .policy import Policy


def input_payload(inputs: Inputs) -> Row:
    sheets = []
    for name, (attribute, headers) in SHEETS.items():
        columns = headers.split()
        rows = getattr(inputs, attribute)
        sheets.append(
            {
                "name": name,
                "keys": columns,
                "labels": columns,
                "rows": [{k: r.get(k) for k in columns} for r in rows],
                "editable": True,
            }
        )
    return {"kind": "inputs", "sheets": sheets}


def delivery_payload(
    results: list[FMIResult], snapshot: Snapshot, policy: Policy, cohort: Row
) -> Row:
    def sheet(name: str, rows: list[Row], keys: list[str] | None = None) -> Row:
        keys = (
            keys
            or list(dict.fromkeys(k for r in rows for k in r))
            or ["analysis_id", "status"]
        )
        return {"name": name, "keys": keys, "labels": keys, "rows": clean(rows)}

    financials = [r for result in results for r in result.financial_periods]
    financial_keys = [
        "analysis_id",
        "entity_id",
        "role",
        "metric",
        "source_row_id",
        "amount",
        "currency",
        "unit_multiplier",
        "scope",
        "period_label",
        "period_start",
        "period_end",
        "period_type",
        "available_at",
        "vintage_verified",
        "source_classification",
        "source_relation",
        "accepted_date",
        "filling_date",
        "crawled_at",
        "correction_events",
        "evidence",
        "historical_status",
    ]
    social_keys = [
        "analysis_id",
        "post_key",
        "profile_id",
        "profile_username",
        "post_id",
        "date_posted",
        "crawled_at",
        "sample",
        "like_count",
        "comment_count",
        "video_view_count",
        "post_type",
        "is_paid_partnership",
        "reviewed",
        "relevant",
        "inclusion_reason",
        "historical_status",
        "post_url",
        "source_relation",
        "source_row_id",
        "evidence",
    ]
    evidence = [
        {
            "kind": "resolved_policy",
            "reference": policy.version,
            "details": json.dumps(policy.model_dump(), sort_keys=True),
        },
        {
            "kind": "cohort",
            "reference": cohort["cohort_id"],
            "details": json.dumps(cohort, sort_keys=True),
        },
        {
            "kind": "limitation",
            "reference": "scenario",
            "details": (
                "Dynamic cohort rescaling can change an unchanged brand's uplift. "
                "The 70–98 range gives every available score positive uplift. "
                "Business scenario, not calibrated predictive accuracy."
            ),
        },
    ]
    evidence.extend(
        {
            "kind": "policy_parameter",
            "reference": k,
            "value": v,
            "details": "Resolved policy",
        }
        for k, v in policy.model_dump().items()
    )
    for kind in (
        "queries",
        "limitations",
        "candidate_mappings",
        "competitor_candidates",
    ):
        evidence.extend(
            {
                "kind": kind,
                "reference": str(i),
                "details": json.dumps(clean(row), sort_keys=True),
            }
            for i, row in enumerate(snapshot.metadata.get(kind, []))
        )
    for row in snapshot.financials:
        evidence.append(
            {
                "kind": "financial_candidate",
                "reference": row["source_row_id"],
                "details": json.dumps(clean(row), sort_keys=True),
            }
        )
    for row in snapshot.overrides:
        evidence.append(
            {
                "kind": "correction_event",
                "reference": str(row.get("event_id")),
                "details": json.dumps(clean(row), sort_keys=True),
            }
        )
    # Full captures remain in the authenticated snapshot. Evidence records their
    # scope/count/hash, avoiding a second giant copy of the same archive in Excel.
    captures = Counter(
        (r.get("source_relation"), r.get("profile_username"))
        for r in snapshot.posts + snapshot.profiles
    )
    snapshot_hash = fingerprint(asdict(snapshot))
    evidence.extend(
        {
            "kind": "social_capture_manifest",
            "reference": snapshot_hash,
            "details": json.dumps(
                {
                    "source_relation": relation,
                    "profile_username": handle,
                    "capture_rows": count,
                    "extracted_at": snapshot.metadata.get("extracted_at"),
                    "status": "source_archive_not_released_historical_metrics",
                },
                sort_keys=True,
            ),
        }
        for (relation, handle), count in sorted(
            captures.items(), key=lambda item: str(item[0])
        )
    )
    return {
        "kind": "delivery",
        "policy": policy.model_dump(),
        "sheets": [
            {
                "name": "Delivery",
                "keys": [f.key for f in FIELDS],
                "labels": [f.label for f in FIELDS],
                "rows": [canonical_record(r.record()) for r in results],
                "fields": [f.record() for f in FIELDS],
            },
            sheet("Financial periods", financials, financial_keys),
            sheet("Peers", [p for r in results for p in r.peers]),
            sheet(
                "Social posts",
                [p for r in results for p in r.social_posts],
                social_keys,
            ),
            sheet("Evidence", evidence),
            sheet(
                "Policy",
                [{"parameter": k, "value": v} for k, v in policy.model_dump().items()],
            ),
            sheet("Fields", [f.record() for f in FIELDS]),
        ],
    }


def write_workbook(
    payload: Row, path: Path, *, previews: bool = False, work_dir: Path | None = None
) -> None:
    """Configured managed artifact runtime; no repo-local dependency installation."""
    node = os.environ.get("FMI_NODE", "node")
    modules = os.environ.get("FMI_NODE_MODULES")
    builder = Path(__file__).with_name("workbook.mjs")
    path.parent.mkdir(parents=True, exist_ok=True)
    artifacts = work_dir or path.parent / ".work"
    artifacts.mkdir(parents=True, exist_ok=True)
    staged = artifacts / path.name
    with tempfile.TemporaryDirectory(prefix="fmi-workbook-") as temp:
        work = Path(temp)
        script = work / "workbook.mjs"
        script.write_bytes(builder.read_bytes())
        if modules:
            (work / "node_modules").symlink_to(Path(modules), target_is_directory=True)
        source = work / "payload.json"
        source.write_text(
            json.dumps(clean(payload), ensure_ascii=False, allow_nan=False)
        )
        command = [
            node,
            str(script),
            str(source),
            str(staged.resolve()),
            str(previews).lower(),
        ]
        try:
            completed = subprocess.run(
                command, check=True, capture_output=True, text=True
            )
        except subprocess.CalledProcessError as exc:
            # Managed JS runtimes may print an entire minified source line.
            # Keep the actual error readable without echoing source/measurements.
            lines = [
                line[:1000] for line in exc.stderr.splitlines() if len(line) < 2000
            ]
            raise RuntimeError(
                "Workbook generation failed: " + "\n".join(lines[-12:])
            ) from exc
        print(completed.stdout)
        staged.replace(path)
