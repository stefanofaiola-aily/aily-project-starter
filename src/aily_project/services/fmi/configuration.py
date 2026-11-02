"""Readable per-brand JSON settings. Measurements stay in database snapshots."""

import csv
import hashlib
import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

from .collection import collected_inputs
from .compact_inputs import SCHEMA as COMPACT_SCHEMA
from .compact_inputs import policy_overrides, read_compact
from .handover import matched_reports, read_reports
from .inputs import (
    SHEETS,
    key,
    merge_reviews,
    read_inputs,
    seed_inputs,
    validate_inputs,
)
from .models import Inputs, Row, calendar_date, clean, show_cutoff, truth
from .policy import Policy

SCHEMA = "fmi-input-v1"
EVENT_ALIASES = {
    "abercromie-fitch": "abercrombie-fitch",
    "the-gap": "gap-inc",
}
IDENTITY_CONTEXT = {"event_category", "event_invited", "fmi_required", "event_names"}


def load_document(path: Path) -> Row:
    data = json.loads(path.read_text())
    if data.get("schema_version") == COMPACT_SCHEMA:
        return data
    if data.get("schema_version") != SCHEMA:
        raise ValueError(f"Expected schema_version {SCHEMA} or {COMPACT_SCHEMA}")
    unknown = set(data) - {
        "schema_version",
        "instructions",
        "policy",
        "query",
        "source_files",
        "brands",
        "peer_entities",
    }
    if unknown:
        raise ValueError(f"Unknown input sections: {sorted(unknown)}")
    return data


def checked_rows(rows: list[Row], sheet: str) -> list[Row]:
    allowed = set(SHEETS[sheet][1].split())
    if sheet == "Entities":
        allowed |= IDENTITY_CONTEXT
    for row in rows:
        unknown = set(row) - allowed
        if unknown:
            raise ValueError(f"{sheet}: unknown fields {sorted(unknown)}")
    return deepcopy(rows)


def read_json_inputs(path: Path) -> Inputs:
    data = load_document(path)
    if data["schema_version"] == COMPACT_SCHEMA:
        return read_compact(path, data)
    result = Inputs(entities=checked_rows(data.get("peer_entities", []), "Entities"))
    for brand in data["brands"]:
        result.entities.extend(checked_rows([brand["identity"]], "Entities"))
        for block in brand["analyses"]:
            result.analyses.extend(checked_rows([block["settings"]], "Analyses"))
            result.peers.extend(checked_rows(block["peers"], "Peers"))
            result.financial_review.extend(
                checked_rows(block["financial_selection"], "Financial review")
            )
            result.post_review.extend(checked_rows(block["post_review"], "Post review"))
    validate_inputs(result)
    return result


def input_policy(path: Path, defaults: Policy) -> Policy:
    if path.suffix.lower() != ".json":
        return defaults
    data = load_document(path)
    overrides = (
        policy_overrides(path, data)
        if data["schema_version"] == COMPACT_SCHEMA
        else data.get("policy", {})
    )
    return Policy.model_validate({**defaults.model_dump(), **overrides})


def query_settings(path: Path) -> Row:
    if path.suffix.lower() != ".json":
        return {}
    query = load_document(path).get("query", {})
    if set(query) - {"first_year", "last_year", "row_limit"}:
        raise ValueError("Only first_year, last_year and row_limit are query settings")
    first, last, limit = (
        query.get(k) for k in ("first_year", "last_year", "row_limit")
    )
    if not (
        isinstance(first, int)
        and isinstance(last, int)
        and isinstance(limit, int)
        and 1900 <= first <= last <= 2100
        and 1 <= limit <= 500000
    ):
        raise ValueError("Set bounded integer query years and row_limit")
    return query


def document(
    inputs: Inputs,
    policy: Policy,
    *,
    reports: list[Row] | None = None,
    sources: list[Row] | None = None,
) -> Row:
    """One brand owns its analyses, peer choices and source-ID review decisions."""
    reports = reports or []

    def full(row: Row, sheet: str) -> Row:
        return {**dict.fromkeys(SHEETS[sheet][1].split()), **clean(row)}

    brands = []
    for entity in inputs.entities:
        if not truth(entity.get("prospect")):
            continue
        blocks = []
        for analysis in inputs.analyses:
            if analysis["entity_id"] != entity["entity_id"]:
                continue
            aid = analysis["analysis_id"]
            blocks.append(
                {
                    "settings": full(analysis, "Analyses"),
                    "peers": [
                        full(r, "Peers")
                        for r in inputs.peers
                        if r["analysis_id"] == aid
                    ],
                    "financial_selection": [
                        full(r, "Financial review")
                        for r in inputs.financial_review
                        if r["analysis_id"] == aid
                    ],
                    "post_review": [
                        full(r, "Post review")
                        for r in inputs.post_review
                        if r["analysis_id"] == aid
                    ],
                }
            )
        refs = matched_reports(entity, reports)
        brands.append(
            {
                "identity": full(entity, "Entities"),
                "analyses": blocks,
                "report_parameters": [
                    {
                        "reference": r["path"],
                        "shows": r["shows"],
                        "annual_windows": r.get("annual_windows", []),
                        "financial_period_labels": r.get("financial_period_labels", []),
                        "handles": r["handles"],
                        "timezones": r["timezones"],
                    }
                    for r in refs
                ],
                "review_tasks": [
                    "Confirm identity, financial scope and any parent proxy",
                    "Approve peer set and fiscal comparability",
                    "Choose analysis route, dates and cutoff",
                    "Select source row IDs and verify eligible financial vintages",
                    "Review social windows, coverage and collection relevance",
                    "Choose dated forecast baseline, target and prior-year actual",
                ],
            }
        )
    return {
        "schema_version": SCHEMA,
        "instructions": {
            "measurements": "Never enter measurements or vintage flags here. "
            "Select database source IDs.",
            "approvals": "Proposals start false. Approvals do not establish "
            "a missing source vintage.",
            "event": "All unique event-list brands require FMI. "
            "A blank invitation flag remains unknown.",
            "legacy_uplift": "Threshold/linear rule uses unrounded raw FMI, as before.",
            "new_uplift": "Exponential rule uses rounded display FMI, as agreed.",
        },
        "policy": policy.model_dump(),
        "query": {"first_year": 2022, "last_year": 2026, "row_limit": 500000},
        "source_files": sources or [],
        "brands": brands,
        "peer_entities": [
            full(e, "Entities") for e in inputs.entities if not truth(e.get("prospect"))
        ],
    }


def event_reconciliation(path: Path, inputs: Inputs, delivery: list[Row]) -> Row:
    """Reconcile every source event row, aliases and duplicate invitations."""
    with path.open(encoding="utf-8-sig", newline="") as source:
        records = [
            r for r in csv.DictReader(source) if r["Brands for FMI Ranking"].strip()
        ]
    names: dict[str, list[str]] = {}
    invited = set()
    for row in records:
        name = row["Brands for FMI Ranking"].strip()
        ident = EVENT_ALIASES.get(key(name), key(name))
        names.setdefault(ident, []).append(name)
        if row["Invited"].strip().upper() == "Y":
            invited.add(ident)
    entities = {e["entity_id"]: e for e in inputs.entities}
    delivered = {r["brand_id"]: r for r in delivery}
    return {
        "source_file": str(path),
        "source_rows": len(records),
        "unique_brands": len(names),
        "invited_yes": len(invited),
        "invitation_unknown": len(names) - len(invited),
        "missing_inputs": sorted(set(names) - entities.keys()),
        "missing_delivery": sorted(set(names) - delivered.keys()),
        "not_mandatory": sorted(
            i
            for i in names
            if i in entities and not truth(entities[i].get("fmi_required"))
        ),
        "invitation_mismatch": sorted(
            i
            for i in names
            if i in delivered
            and delivered[i].get("event_invited") != (True if i in invited else None)
        ),
        "duplicate_brands": {i: n for i, n in names.items() if len(n) > 1},
        "brands": [
            {
                "brand_id": i,
                "source_names": sorted(set(n)),
                "invited": True if i in invited else None,
                "in_inputs": i in entities,
                "in_delivery": i in delivered,
            }
            for i, n in names.items()
        ],
    }


def prepare(
    raw: Path,
    handover: Path,
    policy: Policy,
    *,
    existing: Path | None = None,
    inventory_path: Path | None = None,
) -> Row:
    peer_file = raw / "brand_peers_dinner prospects.xlsx"
    event_file = raw / "FMI index companies(Sheet1).csv"
    inputs = seed_inputs(peer_file)
    if existing:
        inputs = merge_reviews(inputs, read_inputs(existing))
        policy = input_policy(existing, policy)
    reports = read_reports(handover)
    entities = {e["entity_id"]: e for e in inputs.entities}
    # The event file contains duplicate rows and trailing summary columns.
    with event_file.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            name = row["Brands for FMI Ranking"].strip()
            if not name:
                continue
            ident = EVENT_ALIASES.get(key(name), key(name))
            if ident not in entities:
                entities[ident] = {
                    "entity_id": ident,
                    "name": name,
                    "prospect": True,
                    "mapping_approved": False,
                    "evidence": str(event_file),
                }
                aid = ident + "-headline"
                inputs.analyses.append(
                    {
                        "analysis_id": aid,
                        "entity_id": ident,
                        "selected": True,
                        "headline": True,
                        "reviewed": False,
                    }
                )
                inputs.financial_review.extend(
                    {
                        "analysis_id": aid,
                        "entity_id": ident,
                        "role": role,
                        "metric": "revenue",
                        "approved": False,
                    }
                    for role in (
                        "oldest",
                        "earlier",
                        "latest",
                        "baseline",
                        "prior_actual",
                    )
                )
            entity = entities[ident]
            entity.update(
                prospect=True, fmi_required=True, event_category=row["Category"] or None
            )
            entity["event_invited"] = (
                truth(entity.get("event_invited")) or row["Invited"] == "Y" or None
            )
            entity["event_names"] = sorted(set(entity.get("event_names", [])) | {name})
            if key(name) == "the-gap" and not truth(entity.get("mapping_approved")):
                entity.update(
                    proxy=True,
                    proxy_label="Gap Inc. group candidate for The Gap event brand; "
                    "review required",
                )
    inputs.entities = list(entities.values())
    if inventory_path:
        inventory_data = json.loads(inventory_path.read_text())
        if inventory_data.get("authenticated") is not True:
            raise ValueError("Use an authenticated database inventory")
        inputs, reports, _ = collected_inputs(inputs, inventory_data, handover)
    # Make the v1 show windows explicit; these do not adopt a report's 15-day baseline.
    for analysis in inputs.analyses:
        if truth(analysis.get("reviewed")):
            continue
        if (
            analysis.get("route") == "show"
            and analysis.get("show_date")
            and analysis.get("timezone")
        ):
            day = calendar_date(analysis["show_date"])
            analysis.update(
                cutoff=show_cutoff(day, analysis["timezone"]).isoformat(),
                current_start=day.isoformat(),
                current_end=(day + timedelta(days=7)).isoformat(),
                baseline_start=(day - timedelta(days=30)).isoformat(),
                baseline_end=(day + timedelta(days=37)).isoformat(),
            )
        elif not analysis.get("route"):
            refs = matched_reports(entities[analysis["entity_id"]], reports)
            windows = [w for r in refs for w in r.get("annual_windows", [])]
            if len({json.dumps(w, sort_keys=True) for w in windows}) == 1:
                analysis.update(route="annual", **windows[0])
                # Window dates do not establish an assessment cutoff or timezone.
    validate_inputs(inputs)
    files = [peer_file, event_file]
    result = document(
        inputs,
        policy,
        reports=reports,
        sources=[
            {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in files
        ],
    )
    if existing and existing.suffix.lower() == ".json":
        result["query"] = query_settings(existing)
    return result
