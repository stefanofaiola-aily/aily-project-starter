"""One prospect table for Excel/JSON; source context never releases a score."""

from collections import defaultdict
from datetime import timedelta

from .collection import financial_candidates
from .contract import FIELDS, Field, canonical_record
from .issuer_measurements import matches_subject
from .models import (
    FMIResult,
    Inputs,
    Row,
    Snapshot,
    calendar_date,
    fingerprint,
    instant,
    number,
)


def context_fields() -> list[Field]:
    fields = []

    def add(keys: str, group: str, type_: str, unit: str, description: str) -> None:
        for key in keys.split():
            fields.append(
                Field(
                    key,
                    key.replace("_", " ").capitalize(),
                    group,
                    type_,
                    unit,
                    description,
                    "Source context only. Not an eligible historical FMI input.",
                )
            )

    add(
        "actual_revenue_candidate_count forecast_revenue_candidate_count",
        "Source coverage",
        "integer",
        "rows",
        "Retrieved candidate observations, including underlying sources. Not periods.",
    )
    add(
        "revenue_source_status social_source_status score_next_step",
        "Source coverage",
        "string",
        "text",
        "Source availability or remaining review action; not score eligibility.",
    )
    add(
        "observed_context_historical_eligible",
        "Source context",
        "boolean",
        "boolean",
        "Always false. Observed context is not released historical app data.",
    )
    add(
        "observed_target_forecast_candidate_count",
        "Observed target forecast",
        "integer",
        "rows",
        "Light revenue forecast rows whose native reported_date equals the requested "
        "target end. End-date matching does not verify the complete fiscal period.",
    )
    add(
        "observed_target_forecast_amount",
        "Observed target forecast",
        "number",
        "native_source_amount_unknown_scale",
        "Unique native Light forecast amount with matching target end date. "
        "Not the reviewed baseline; currency, scope, scale and vintage need review.",
    )
    add(
        "observed_target_forecast_status observed_target_forecast_source_row_id "
        "observed_target_forecast_source_relation observed_target_forecast_period",
        "Observed target forecast",
        "string",
        "text",
        "Native target candidate and source provenance, never an eligible baseline.",
    )
    add(
        "observed_target_forecast_date",
        "Observed target forecast",
        "date",
        "calendar_date",
        "Native reported_date. Not a forecast publication or vintage timestamp.",
    )
    add(
        "observed_revenue_amount",
        "Observed revenue",
        "number",
        "native_source_amount_unknown_scale_if_multiplier_null",
        "Latest unique dated consolidated-view actual candidate, without aggregation. "
        "May be estimated/interpolated. Verify scope, units and vintage before use.",
    )
    add(
        "observed_revenue_period observed_revenue_currency observed_revenue_symbol "
        "observed_revenue_scope observed_revenue_source_relation "
        "observed_revenue_source_row_id observed_revenue_source_classification "
        "observed_revenue_status",
        "Observed revenue",
        "string",
        "text",
        "Native candidate metadata. Unknown scope/currency stays null. "
        "Period labels are not interpreted as reported standalone quarters.",
    )
    add(
        "observed_revenue_date",
        "Observed revenue",
        "date",
        "calendar_date",
        "Native source period date, not publication date or verified vintage.",
    )
    add(
        "observed_revenue_unit_multiplier",
        "Observed revenue",
        "number",
        "currency_units_per_stored_unit",
        "Source scale if supplied; never assume one when missing.",
    )
    add(
        "observed_social_month observed_social_previous_month observed_social_status",
        "Observed Instagram",
        "string",
        "text",
        "Latest observed UTC publication month before the extraction month. "
        "Archive may be incomplete. Previous means preceding calendar month.",
    )
    add(
        "observed_social_total_posts observed_social_previous_total_posts",
        "Observed Instagram",
        "integer",
        "posts",
        "Retained dated captures, not complete account activity.",
    )
    add(
        "observed_social_latest_capture",
        "Observed Instagram",
        "datetime",
        "UTC",
        "Latest capture in the displayed publication cohort; not historical replay.",
    )
    for metric in ("likes", "comments", "views"):
        add(
            f"observed_social_median_{metric} observed_social_previous_median_{metric}",
            "Observed Instagram",
            "number",
            "count",
            "Median of nonnegative observations for this metric. Missing is not zero.",
        )
        add(
            f"observed_social_usable_{metric} observed_social_previous_usable_{metric}",
            "Observed Instagram",
            "integer",
            "posts",
            "Metric-specific usable denominator; never substitutes for likes.",
        )
        add(
            f"observed_social_{metric}_change",
            "Observed Instagram",
            "number",
            "fraction",
            "Current median / previous-calendar-month median - 1; "
            "missing/zero prior gives null. Observed cohorts, not controlled FMI.",
        )
    return fields


CONTEXT_FIELDS = context_fields()


def observed_target_forecast(rows: list[Row], analysis: Row) -> Row:
    """Match dates, not fiscal quarter names; do not release a baseline."""
    target = analysis.get("forecast_target_end")
    if not target:
        return {"observed_target_forecast_status": "missing_forecast_target"}
    end = calendar_date(target)
    candidates = []
    for row in rows:
        if (
            row.get("source_relation") != "ai.light_financial_statements_forecast"
            or row.get("metric") != "revenue"
            or row.get("kind") != "forecast"
            or not row.get("source_row_id")
            or number(row.get("amount")) is None
        ):
            continue
        try:
            matches = calendar_date(row.get("reported_date")) == end
        except (ValueError, TypeError):
            matches = False
        if matches:
            candidates.append(row)
    unique = {fingerprint(r): r for r in candidates}
    result: Row = {"observed_target_forecast_candidate_count": len(unique)}
    if len(unique) != 1:
        result["observed_target_forecast_status"] = (
            "no_native_forecast_with_requested_end_date"
            if not unique
            else "conflicting_target_candidates_review_required"
        )
        return result
    row = next(iter(unique.values()))
    result.update(
        observed_target_forecast_amount=number(row["amount"]),
        observed_target_forecast_date=end.isoformat(),
        observed_target_forecast_period=row.get("period_label"),
        observed_target_forecast_source_row_id=row["source_row_id"],
        observed_target_forecast_source_relation=row["source_relation"],
        observed_target_forecast_status="end_date_match_only_scope_period_and_vintage_unverified",
    )
    return result


def observed_revenue(rows: list[Row], snapshot: Snapshot) -> Row:
    """Expose one native observation, never manufacture comparable revenue."""
    extracted = instant(snapshot.metadata.get("extracted_at"))
    candidates = []
    for row in rows:
        if (
            row.get("source_relation") != "normalized.v_finance_financial_statements"
            or row.get("kind") != "actual"
            or row.get("metric") != "revenue"
            or number(row.get("amount")) is None
            or not row.get("date")
            or not row.get("source_row_id")
        ):
            continue
        try:
            day = calendar_date(row["date"])
        except (TypeError, ValueError):
            continue
        if extracted is not None and day <= extracted.date():
            candidates.append((day, row))
    if not candidates:
        return {"observed_revenue_status": "no_dated_consolidated_candidate"}
    latest = max(day for day, _ in candidates)
    selected = {fingerprint(r): r for d, r in candidates if d == latest}
    # Source conflicts cannot be settled by choosing the first row.
    if len(selected) != 1:
        return {"observed_revenue_status": "multiple_latest_candidates_review_required"}
    row = next(iter(selected.values()))
    return {
        "observed_revenue_amount": number(row["amount"]),
        "observed_revenue_date": latest.isoformat(),
        "observed_revenue_period": row.get("period_label"),
        **{
            f"observed_revenue_{key}": row.get(key)
            for key in (
                "currency",
                "unit_multiplier",
                "symbol",
                "scope",
                "source_relation",
                "source_row_id",
                "source_classification",
            )
        },
        "observed_revenue_status": "unreviewed_native_observation_not_score_input",
    }


def flat_payload(
    results: list[FMIResult],
    inputs: Inputs,
    snapshot: Snapshot,
    contexts: list[Row],
) -> Row:
    entities = {e["entity_id"]: e for e in inputs.entities}
    analyses = {a["analysis_id"]: a for a in inputs.analyses}
    months: dict[str, list[Row]] = defaultdict(list)
    extracted = instant(snapshot.metadata.get("extracted_at"))
    final_month = (
        (extracted.date().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        if extracted
        else None
    )
    for context in contexts:
        if final_month and context["month"] <= final_month:
            months[context["brand_id"]].append(context)
    rows = []
    for result in results:
        row = canonical_record(result.record())
        entity = {
            **entities[result.brand_id],
            **{
                k: result.values[k]
                for k in ("light_code", "ticker", "shared_symbol")
                if k in result.values
            },
        }
        candidates = financial_candidates(entity, snapshot)
        # Segment tables can be matched by verified subject even without a brand
        # ticker. Include them in coverage counts without importing group forecasts.
        definition = (
            analyses.get(result.analysis_id, {})
            .get("dossier", {})
            .get("financial", {})
            .get("entities", {})
            .get(result.brand_id, {})
        )
        if definition:
            candidates = list(
                {
                    r.get("source_row_id") or fingerprint(r): r
                    for r in [
                        *candidates,
                        *(
                            r
                            for r in snapshot.financials
                            if matches_subject(r, definition)
                        ),
                    ]
                }.values()
            )
        for kind in ("actual", "forecast"):
            row[f"{kind}_revenue_candidate_count"] = sum(
                r.get("metric") == "revenue" and r.get("kind") == kind
                for r in candidates
            )
        row["revenue_source_status"] = (
            "verified_dossier_measurements_retrieved"
            if row.get("financial_coverage_status") == "verified_dossier_measurements"
            else "candidates_retrieved_review_required"
            if row["actual_revenue_candidate_count"]
            else "no_matching_actual_revenue_rows"
        )
        row["social_source_status"] = (
            "eligible_social_samples_retrieved"
            if row.get("social_score") is not None
            else "captures_retrieved_review_required"
            if row.get("social_capture_count")
            else "no_matching_instagram_captures"
        )
        row["observed_context_historical_eligible"] = False
        row["score_next_step"] = (
            "Presentation simulation; review scope, period proxies and relevance "
            "before production use"
            if row["fmi_status"] == "available"
            and row.get("calculation_mode") == "presentation"
            else "Dossier-defined retrospective score; verify source coverage "
            "and compatible forecast; not point-in-time replay"
            if row["fmi_status"] == "available"
            and row.get("calculation_mode") == "dossier"
            else "Released reviewed score"
            if row["fmi_status"] == "available"
            else "Review identity/scope, analysis dates, three revenue periods, "
            "peer set and eligible social samples. See missing reasons."
        )
        row.update(observed_revenue(candidates, snapshot))
        row.update(
            observed_target_forecast(candidates, analyses.get(result.analysis_id, {}))
        )
        available = months.get(result.brand_id, [])
        latest = max(available, key=lambda r: r["month"]) if available else None
        row["observed_social_status"] = (
            "current_capture_incomplete_archive_not_historical_replay"
            if latest
            else "no_dated_capture_publication_cohort_before_extraction_month"
        )
        if latest:
            previous = next(
                (r for r in available if r["month"] == latest["previous_month"]), {}
            )
            row.update(
                observed_social_month=latest["month"],
                observed_social_previous_month=latest["previous_month"],
                observed_social_latest_capture=latest["latest_capture"],
                observed_social_total_posts=latest["total_posts"],
                observed_social_previous_total_posts=previous.get("total_posts"),
            )
            for label, metric in (
                ("likes", "like_count"),
                ("comments", "comment_count"),
                ("views", "video_view_count"),
            ):
                for prefix in ("", "previous_"):
                    for stat in ("median", "usable"):
                        row[f"observed_social_{prefix}{stat}_{label}"] = latest.get(
                            f"{prefix}{stat}_{metric}"
                        )
                row[f"observed_social_{label}_change"] = latest.get(
                    f"median_{metric}_change"
                )
        rows.append(row)
    fields = [*FIELDS, *CONTEXT_FIELDS]
    # Identity and dinner membership remain visible before the main results.
    first = ["name", "brand_id", "fmi_required", "event_invited"]
    first.extend(f.key for f in FIELDS if f.group == "Headline" and f.key not in first)
    first.extend(f.key for f in CONTEXT_FIELDS if f.group == "Source coverage")
    by_key = {f.key: f for f in fields}
    keys = list(dict.fromkeys([*first, *(f.key for f in fields)]))
    return {
        "kind": "flat-delivery",
        "sheets": [
            {
                "name": "Delivery",
                "keys": keys,
                "labels": [by_key[k].label for k in keys],
                "fields": [by_key[k].record() for k in keys],
                "rows": [
                    {k: None if row.get(k) == "" else row.get(k) for k in keys}
                    for row in rows
                ],
            }
        ],
    }
