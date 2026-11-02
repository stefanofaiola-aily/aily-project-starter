"""Per-brand calculation records and explicitly non-historical source context."""

import json
from collections import defaultdict
from pathlib import Path
from statistics import median

from .collection import financial_candidates
from .handover import names
from .inputs import as_dict
from .models import (
    FMIResult,
    Inputs,
    Row,
    Snapshot,
    clean,
    fingerprint,
    instant,
    number,
    truth,
)
from .policy import Policy


def monthly_context(inputs: Inputs, snapshot: Snapshot) -> list[Row]:
    """Current-capture publication cohorts, NOT historical app score drivers."""
    extracted = instant(snapshot.metadata.get("extracted_at"))
    accounts: dict[str, list[Row]] = defaultdict(list)
    for post in snapshot.posts:
        accounts[str(post.get("profile_username") or "").lower()].append(post)
    records = []
    for entity in inputs.entities:
        if not truth(entity.get("prospect")) or not entity.get("handle"):
            continue
        retained: dict[str, Row] = {}
        for post in accounts[str(entity["handle"]).lower()]:
            stable_id = post.get("post_id") or post.get("post_url")
            if not stable_id:
                continue
            identity = (
                str(post.get("profile_id") or entity["handle"]) + ":" + str(stable_id)
            )
            stamp = instant(post.get("crawled_at"))
            posted = instant(post.get("date_posted"))
            if (
                stamp is None
                or posted is None
                or stamp < posted
                or extracted is not None
                and stamp > extracted
            ):
                continue
            old = retained.get(identity)
            old_stamp = instant(old["crawled_at"]) if old else None
            if old_stamp is None or stamp > old_stamp:
                retained[identity] = post
            elif (
                old is not None
                and stamp == old_stamp
                and any(
                    post.get(k) != old.get(k)
                    for k in ("like_count", "comment_count", "video_view_count")
                )
            ):
                # A same-time conflicting observation is not a reliable candidate.
                retained[identity] = {**old, "conflicting_capture": True}
        months: dict[str, list[Row]] = defaultdict(list)
        for post in retained.values():
            if not post.get("conflicting_capture"):
                posted = instant(post["date_posted"])
                assert posted is not None
                months[posted.strftime("%Y-%m")].append(post)
        indexed = {}
        for month, posts in sorted(months.items()):
            captures = [t for p in posts if (t := instant(p["crawled_at"])) is not None]
            row: Row = {
                "brand_id": entity["entity_id"],
                "name": entity["name"],
                "handle": entity["handle"],
                "month": month,
                "publication_timezone": "UTC",
                "total_posts": len(posts),
                "earliest_capture": min(captures).isoformat(),
                "latest_capture": max(captures).isoformat(),
                "historical_status": "current_capture_context_not_historical_replay",
                "influences_fmi": False,
                "coverage_status": "observed_archive_not_complete_account_activity",
            }
            for metric in ("like_count", "comment_count", "video_view_count"):
                values = [
                    v
                    for p in posts
                    if (v := number(p.get(metric))) is not None and v >= 0
                ]
                row[f"usable_{metric}"] = len(values)
                row[f"median_{metric}"] = median(values) if values else None
            year, month_number = map(int, month.split("-"))
            previous = (
                f"{year - 1}-12"
                if month_number == 1
                else f"{year}-{month_number - 1:02d}"
            )
            row["previous_month"] = previous
            prior = indexed.get(previous, {})
            for metric in ("like_count", "comment_count", "video_view_count"):
                before, current = prior.get(f"median_{metric}"), row[f"median_{metric}"]
                row[f"previous_median_{metric}"] = before
                row[f"previous_usable_{metric}"] = prior.get(f"usable_{metric}")
                row[f"median_{metric}_change"] = (
                    current / before - 1
                    if before is not None and before > 0 and current is not None
                    else None
                )
            indexed[month] = row
            records.append(row)
    return clean(records)


def historical_comparison(results: list[FMIResult], path: Path | None) -> list[Row]:
    if path is None:
        return []
    historical = json.loads(path.read_text())
    rows = []
    for result in results:
        variants = names(str(result.values.get("name"))) | names(result.brand_id)
        matches = [
            r for r in historical["deliveryRows"] if names(r["prospect"]) & variants
        ]
        match = matches[0] if len(matches) == 1 else {}
        old, current = number(match.get("overallScore")), result.values.get("raw_fmi")
        rows.append(
            {
                "brand_id": result.brand_id,
                "name": result.values.get("name"),
                "historical_reported_overall": old,
                "historical_display_fmi": number(
                    match.get("normalizedFashionMomentumIndex")
                ),
                "historical_ir_score": number(match.get("momentumScore")),
                "historical_social_score": number(match.get("socialScore")),
                "historical_trend_score": number(match.get("strengthScore")),
                "current_ir_score": result.values.get("ir_score"),
                "current_social_score": result.values.get("social_score"),
                "current_trend_score": result.values.get("trend_score"),
                "current_raw_fmi": current,
                "current_display_fmi": result.values.get("display_fmi"),
                "raw_difference": current - old
                if current is not None and old is not None
                else None,
                "comparison_status": "scope/window differences require review"
                if match
                else "no_unique_historical_match",
                "reference_status": "audit_reference_only_not_production_measurement",
                "source_reference": str(path),
                "source_as_of": historical.get("dataAsOf"),
                "limitations": "Historical totals may be rounded, use later captures, "
                "narrower baselines, alternate Trend and proxy scopes. "
                "Never substituted for DB measurements.",
            }
        )
    return rows


def context_sheet(name: str, rows: list[Row]) -> Row:
    keys = list(dict.fromkeys(k for r in rows for k in r)) or ["brand_id", "status"]
    fields = []
    for key in keys:
        type_, unit = "string", "text"
        if key.endswith("_change"):
            type_, unit = "number", "fraction"
        elif "median_" in key:
            type_, unit = "number", "count"
        elif "usable_" in key or key == "total_posts":
            type_, unit = "integer", "count"
        elif key.endswith("_capture"):
            type_, unit = "datetime", "UTC"
        elif key in {
            "current_raw_fmi",
            "current_display_fmi",
            "historical_reported_overall",
            "historical_display_fmi",
            "raw_difference",
        } or key.endswith("_score"):
            type_, unit = "number", "score_0_100"
            if key == "raw_difference":
                unit = "score_points"
        fields.append({"field_key": key, "type": type_, "unit": unit})
    return {
        "name": name,
        "keys": keys,
        "labels": [k.replace("_", " ").capitalize() for k in keys],
        "rows": rows,
        "fields": fields,
    }


def output_dictionary(sheets: list[Row]) -> list[Row]:
    """Describe every exported sheet/column, not just the headline record."""
    entries = []
    for sheet in sheets:
        if sheet["name"] == "Fields":
            continue
        declared = {f["field_key"]: f for f in sheet.get("fields", [])}
        for key, label in zip(sheet["keys"], sheet["labels"], strict=True):
            context = sheet["name"] in {
                "Financial candidates",
                "Social annual snapshots",
                "Social monthly context",
                "Historical comparison",
            }
            values = [
                r.get(key) for r in sheet.get("rows", []) if r.get(key) is not None
            ]
            sample = values[0] if values else None
            inferred = (
                "boolean"
                if isinstance(sample, bool)
                else "integer"
                if isinstance(sample, int)
                else "number"
                if isinstance(sample, float)
                else "array"
                if isinstance(sample, list)
                else "object"
                if isinstance(sample, dict)
                else "string"
            )
            inferred_unit = {
                "boolean": "boolean",
                "integer": "count",
                "number": "number",
                "array": "json_array",
                "object": "json_object",
            }.get(inferred, "text")
            if key == "amount":
                inferred, inferred_unit = "number", "currency_times_unit_multiplier"
            elif key == "unit_multiplier":
                inferred, inferred_unit = "number", "currency_unit_multiplier"
            elif key == "year":
                inferred, inferred_unit = "integer", "year_number"
            elif key in {"period_start", "period_end", "show_date"}:
                inferred, inferred_unit = "date", "calendar_date"
            elif key in {"available_at", "crawled_at", "accepted_date", "filling_date"}:
                inferred, inferred_unit = "datetime", "source_timestamp"
            elif key in {
                "approved",
                "comparable",
                "reviewed",
                "relevant",
                "vintage_verified",
            }:
                inferred, inferred_unit = "boolean", "boolean"
            descriptions = {
                "amount": "Source amount. Verify currency, scope and units before use.",
                "source_row_id": "Stable observation ID joining the source snapshot.",
                "unit_multiplier": "Scale to currency units. Unknown stays null.",
                "vintage_verified": "Verified historical version, not simply approved.",
                "month": "UTC publication month of latest valid dated captures.",
                "total_posts": "Retained observed posts, not a full account census.",
                "previous_month": "Previous calendar month. Archive gaps stay missing.",
                "historical_status": "Use classification; context is not replay.",
                "historical_reported_overall": "Old, potentially rounded audit score.",
                "raw_difference": "Current raw minus old. Scope/windows may differ.",
                "coverage_status": "Observed archive coverage, not complete activity.",
                "value": "Policy/provenance value with mixed JSON scalar types.",
            }
            description = descriptions.get(key, label)
            if (
                "median_" in key
                and context
                and sheet["name"] != "Historical comparison"
            ):
                description = (
                    "Median of numeric nonnegative observations, excluding missing; "
                    + label.lower()
                )
                if key.endswith("_change"):
                    description = "Current / preceding-calendar-month median - 1. "
                    "Missing or zero denominator stays null."
            elif "usable_" in key and context:
                description = "Numeric nonnegative observations for this metric, "
                "excluding missing values."
            entry = {
                "sheet_name": sheet["name"],
                "group": sheet["name"],
                "field_key": key,
                "excel_label": label,
                "description": description,
                "type": inferred,
                "unit": inferred_unit,
                "required": False,
                "influences_fmi": False,
                "derivation": "Context only, not eligible historical score input"
                if context
                else "Canonical service result or provenance",
                **declared.get(key, {}),
            }
            if (
                inferred in {"boolean", "integer", "number", "array", "object"}
                and entry["type"] == "string"
            ):
                entry["type"] = inferred
            entry["description"] = (
                declared.get(key, {}).get("description") or description
            )
            if key == "value":
                entry["type"] = "json_scalar"
            entries.append(entry)
    return entries


def write_brand_records(
    inputs: Inputs,
    snapshot: Snapshot,
    results: list[FMIResult],
    policy: Policy,
    directory: Path,
    *,
    contexts: list[Row],
    comparisons: list[Row],
) -> None:
    """Document selected measurements and separately label unused candidates."""
    directory.mkdir(parents=True, exist_ok=True)
    entities = {e["entity_id"]: e for e in inputs.entities}
    query_ids = {
        q["source_relation"]: i
        for i, q in enumerate(snapshot.metadata.get("queries", []))
    }
    index = [
        "# Brand calculation records",
        "",
        "Database snapshot: " + snapshot.metadata["extracted_at"],
        "",
        "| Brand | Mandatory event FMI | FMI status | Run record |",
        "| --- | --- | --- | --- |",
    ]
    for result in results:
        entity = entities[result.brand_id]
        candidates = financial_candidates(entity, snapshot)
        selections = [
            r for r in inputs.financial_review if r["analysis_id"] == result.analysis_id
        ]
        candidate_records = [
            {
                k: clean(r.get(k))
                for k in (
                    "source_row_id",
                    "source_relation",
                    "metric",
                    "kind",
                    "amount",
                    "currency",
                    "unit_multiplier",
                    "scope",
                    "period_label",
                    "period_start",
                    "period_end",
                    "available_at",
                    "vintage_verified",
                    "source_classification",
                )
            }
            | {
                "query_index": query_ids.get(r["source_relation"]),
                "status": "candidate_not_used_unless_selected_and_eligible",
            }
            for r in candidates
            if r.get("source_row_id")
            not in {p.get("source_row_id") for p in result.financial_periods}
        ]
        record = {
            "brand_id": result.brand_id,
            "run_id": result.values["run_id"],
            "source_extracted_at": snapshot.metadata["extracted_at"],
            "input_hash": fingerprint(as_dict(inputs)),
            "identity": entity,
            "analyses": [
                a for a in inputs.analyses if a["entity_id"] == result.brand_id
            ],
            "financial_selection": selections,
            "policy": policy.model_dump(),
            "calculation": result.record(),
            "selected_financial_periods": result.financial_periods,
            "peer_calculations": result.peers,
            "selected_social_posts": result.social_posts,
            "unused_financial_candidates": candidate_records,
            "current_social_context": [
                r for r in contexts if r["brand_id"] == result.brand_id
            ],
            "historical_reference": [
                r for r in comparisons if r["brand_id"] == result.brand_id
            ],
            "query_manifest": snapshot.metadata.get("queries", []),
        }
        path = directory / result.brand_id
        path.with_suffix(".json").write_text(
            json.dumps(clean(record), indent=2, ensure_ascii=False, allow_nan=False)
            + "\n"
        )
        v = result.values
        social_metric = v.get("social_scoring_metric", "likes")
        lines = [
            f"# {entity['name']} FMI run",
            "",
            f"Run: `{v['run_id']}`. "
            f"Database snapshot: {snapshot.metadata['extracted_at']}.",
            "",
            f"FMI status: **{v.get('fmi_status')}**. "
            f"Forecast status: **{v.get('forecast_status')}**.",
            f"Calculation mode: {v.get('calculation_mode', 'strict_replay')}. "
            "Release: "
            f"{v.get('release_status', 'reviewed historical inputs required')}. "
            "Financial basis: "
            f"{v.get('financial_unit_status', 'reviewed source units')}. "
            f"Social basis: {v.get('social_selection_basis', 'reviewed relevance')}. "
            "Native quarter proxies and current captures are not strict "
            "historical evidence.",
            f"Revenue selection: {v.get('financial_selection_basis')}. "
            f"Latest actual age: {v.get('latest_actual_age_days')} days. "
            f"Peer periods: {v.get('used_peer_periods')}. "
            f"Peer alignment: {v.get('peer_calendar_alignment_status')}.",
            f"Requested forecast: {v.get('forecast_target_label')}. "
            f"Selected native forecast: {v.get('baseline_period_label')} "
            f"ending {v.get('baseline_period_end')}. "
            f"Alignment: {v.get('forecast_calendar_alignment_status')}. "
            f"Forecast YoY actual: {v.get('prior_year_actual_period_label')} "
            f"ending {v.get('prior_year_actual_period_end')}.",
            "",
            "## Inputs and retrieval",
            "",
            f"Light code used: {v.get('light_code') or 'unresolved'}. "
            f"Ticker used: {v.get('ticker') or 'unresolved'}. "
            f"Shared symbol used: {v.get('shared_symbol') or 'unresolved'}.",
            f"Financial subject used: {v.get('financial_subject') or 'unresolved'}. "
            f"Scope: {v.get('scope') or 'unreviewed'}. "
            f"Proxy: {v.get('proxy_label') or 'none'}.",
            f"Parent route: {v.get('parent_fallback_status')}. "
            f"Ownership evidence: {v.get('parent_mapping_evidence')}. "
            f"Currency basis: {v.get('financial_currency_status')}.",
            f"Instagram: {entity.get('handle') or 'unresolved'}. "
            "Full SQL, bind scopes and source IDs are in the accompanying JSON.",
            "",
            "## Calculation",
            "",
            "Growth = current / prior - 1. Peer gap = 100 × "
            "(brand growth - selected-peer median growth), in pp.",
            f"Used peers: {v.get('used_peer_names', v.get('approved_peer_names'))}. "
            f"Excluded peers: {v.get('peer_exclusion_reasons') or 'none'}.",
            f"Revenue periods (oldest/earlier/latest): {v.get('oldest_period_end')}/"
            f"{v.get('earlier_period_end')}/{v.get('latest_period_end')}. "
            f"Earlier/latest brand growth: {v.get('earlier_growth')}/"
            f"{v.get('latest_growth')}. "
            f"Earlier/latest peer median growth: {v.get('earlier_peer_median_growth')}/"
            f"{v.get('latest_peer_median_growth')}. "
            f"Earlier/latest gaps (pp): {v.get('earlier_gap_pp')}/"
            f"{v.get('latest_gap_pp')}.",
            f"Social current/baseline windows: {v.get('current_window')}/"
            f"{v.get('baseline_window')}. "
            f"Usable posts: {v.get('current_usable_posts')}/"
            f"{v.get('baseline_usable_posts')}. "
            f"Median {social_metric}: {v.get(f'current_median_{social_metric}')}/"
            f"{v.get(f'baseline_median_{social_metric}')}. "
            f"Lift: {v.get(f'{social_metric}_lift')}. "
            f"Portfolio members: {v.get('social_used_members')}.",
            "IR = clip(50 + configured multiplier × latest gap). "
            f"Social = clip(50 + 100 × {social_metric} lift).",
            f"Trend basis: {v.get('trend_basis', 'peer_gap')}. "
            f"Comparison: {v.get('trend_comparison')}; "
            f"change: {v.get('trend_change_pp')} pp.",
            "Trend tests improving, declining, then sustained outperformance, "
            "in that order.",
            f"Raw FMI = {policy.ir_weight} × IR + {policy.social_weight} × Social "
            f"+ {policy.trend_weight} × Trend.",
            f"Raw FMI: {v.get('raw_fmi')}. Display FMI: {v.get('display_fmi')}. "
            f"IR/Social/Trend: {v.get('ir_score')}/{v.get('social_score')}/"
            f"{v.get('trend_score')}.",
            f"Legacy uplift = 0 at raw FMI ≤ {policy.legacy_uplift_threshold}; "
            f"otherwise {policy.legacy_uplift_intercept} + (raw FMI - threshold) "
            f"× {policy.legacy_uplift_per_score}.",
            f"New uplift = {policy.uplift_max} × expm1({policy.uplift_exponent} "
            f"× display FMI / 100) / expm1({policy.uplift_exponent}).",
            f"Legacy/new rates: {v.get('legacy_uplift_fraction')}/"
            f"{v.get('uplift_fraction')}. Baseline: {v.get('baseline_revenue')}. "
            f"Adjusted legacy/new forecasts: {v.get('legacy_adjusted_forecast')}/"
            f"{v.get('adjusted_forecast')}.",
            "",
            "## Selected financial observations",
            "",
            "| Entity | Metric | Role | Amount (native units) | Currency | "
            "Native period | Selected end | Source ID |",
            "| --- | --- | --- | ---: | --- | --- | --- | --- |",
        ]
        for row in result.financial_periods:
            lines.append(
                f"| {row['entity_id']} | {row['metric']} | {row['role']} | "
                f"{row['amount']} | {row['currency'] or 'unknown'} | "
                f"{row['period_label']} | {row['period_end']} | "
                f"{row['source_row_id']} |"
            )
        if not result.financial_periods:
            lines.extend(
                [
                    "",
                    "No eligible reviewed revenue observations were selected. "
                    "Candidate amounts are not calculation inputs.",
                ]
            )
        lines.extend(["", "## Exact dossier reference (not current measurements)", ""])
        for reference in comparisons:
            if reference["brand_id"] == result.brand_id and reference.get(
                "dossier_source"
            ):
                lines.extend(
                    [
                        f"Source: {reference['dossier_source']}. "
                        f"SHA256: {reference.get('dossier_source_sha256')}.",
                        f"Headline: {reference.get('dossier_headline_fmi')}. "
                        f"Original raw: {reference.get('dossier_original_raw_fmi')}. "
                        f"Basis: {reference.get('dossier_score_basis')}. "
                        f"Arithmetic: {reference.get('dossier_arithmetic_status')}.",
                        str(reference.get("dossier_headline_evidence") or ""),
                        str(reference.get("dossier_period_evidence") or ""),
                        "Scope/windows and normalization differ; "
                        "NOT a like-for-like performance change.",
                    ]
                )
        lines.extend(["", "## Missing inputs", ""])
        lines.extend(f"- {reason}" for reason in dict.fromkeys(result.gaps))
        lines.append(f"- Forecast: {v.get('forecast_missing_reason') or 'none'}")
        lines.extend(
            [
                "",
                "## Unused source context",
                "",
                f"{len(candidates)} financial metric candidates are recorded in JSON. "
                "Current-capture social months and historical scores are context only. "
                "They do not substitute for eligible historical measurements.",
                "",
            ]
        )
        path.with_suffix(".md").write_text("\n".join(lines))
        index.append(
            f"| {entity['name']} | {truth(entity.get('fmi_required'))} | "
            f"{v.get('fmi_status')} | [{entity['name']}]({result.brand_id}.md) |"
        )
    (directory / "INDEX.md").write_text("\n".join(index) + "\n")
