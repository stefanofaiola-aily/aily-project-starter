"""Reviewed financial selections, with fail-closed historical eligibility."""

from datetime import datetime

from .models import Inputs, Row, Snapshot, calendar_date, instant, number, truth


def identity_ready(entity: Row) -> bool:
    return bool(
        truth(entity.get("mapping_approved"))
        and entity.get("evidence")
        and entity.get("financial_subject")
        and entity.get("scope")
        and (entity.get("light_code") or entity.get("shared_symbol"))
        and (not truth(entity.get("proxy")) or entity.get("proxy_label"))
    )


def symbols(entity: Row) -> set[str]:
    result = {str(entity["shared_symbol"])} if entity.get("shared_symbol") else set()
    if truth(entity.get("mapping_approved")) and entity.get("evidence"):
        result.update(
            x.strip() for x in str(entity.get("aliases") or "").split(";") if x.strip()
        )
    return result


def eligible(row: Row, cutoff: datetime | None) -> tuple[bool, str]:
    if cutoff is None:
        return False, "missing_cutoff"
    available = instant(row.get("available_at"))
    if available is None:
        return False, "missing_historical_vintage"
    if available > cutoff:
        return False, "post_cutoff_vintage"
    if "corrected" in str(row.get("source_classification", "")):
        corrections = row.get("correction_events") or []
        if not corrections:
            return False, "missing_correction_provenance"
        dates = [instant(e.get("changed_at")) for e in corrections]
        if any(t is None or t > cutoff for t in dates):
            return False, "post_cutoff_or_unknown_correction"
    if not truth(row.get("vintage_verified")):
        return False, "unverified_historical_vintage"
    if not row.get("source_relation") or not row.get("source_row_id"):
        return False, "missing_source_provenance"
    return True, "eligible"


def select(
    inputs: Inputs,
    snapshot: Snapshot,
    analysis_id: str,
    entity: Row,
    role: str,
    metric: str,
    cutoff: datetime | None,
) -> tuple[Row | None, str]:
    reviews = [
        r
        for r in inputs.financial_review
        if r.get("analysis_id") == analysis_id
        and r.get("entity_id") == entity["entity_id"]
        and r.get("role") == role
        and r.get("metric") == metric
    ]
    if len(reviews) != 1 or not truth(reviews[0].get("approved")):
        return None, "financial_selection_unreviewed"
    review = reviews[0]
    if not review.get("evidence") or not identity_ready(entity):
        return None, "identity_or_selection_evidence_missing"
    candidates = [
        r
        for r in snapshot.financials
        if r.get("source_row_id") == review.get("source_row_id")
    ]
    if len(candidates) != 1:
        return None, "financial_source_missing_or_conflicting"
    row = dict(candidates[0])
    if row.get("metric") != metric:
        return None, "metric_mismatch"
    shared = str(row.get("source_relation", "")).startswith(
        ("normalized.", "denormalized.")
    )
    if (shared and row.get("symbol") not in symbols(entity)) or (
        not shared and row.get("company_code") != entity.get("light_code")
    ):
        return None, "financial_identity_mismatch"
    valid, reason = eligible(row, cutoff)
    if not valid:
        return None, reason
    if role == "baseline" and row.get("kind") != "forecast":
        return None, "forecast_requires_forecast_source"
    if role != "baseline" and row.get("kind") != "actual":
        return None, "actual_requires_actual_source"
    if review.get("aggregation_definition") not in (
        None,
        "",
        "single_observation",
        "reported_annual",
    ):
        return None, "aggregation_not_supported_requires_verified_source_period"
    # Review supplies semantic labels, never amounts or availability timestamps.
    for column in (
        "scope",
        "currency",
        "unit_multiplier",
        "period_label",
        "period_start",
        "period_end",
        "period_type",
    ):
        native = row.get(column)
        reviewed = review.get(column)
        if native not in (None, "") and reviewed not in (None, ""):
            if column in ("period_start", "period_end"):
                try:
                    same = calendar_date(native) == calendar_date(reviewed)
                except (ValueError, TypeError):
                    return None, "invalid_reviewed_period_boundary"
            elif column == "unit_multiplier":
                same = number(native) == number(reviewed)
            else:
                same = str(native) == str(reviewed)
            if not same:
                return None, f"conflicting_{column}"
        row[column] = native if native not in (None, "") else reviewed
    if any(
        row.get(c) in (None, "")
        for c in (
            "scope",
            "currency",
            "unit_multiplier",
            "period_label",
            "period_start",
            "period_end",
            "period_type",
        )
    ):
        return None, "missing_financial_semantics"
    amount, unit = number(row.get("amount")), number(row.get("unit_multiplier"))
    if (
        amount is None
        or unit is None
        or unit <= 0
        or (metric == "revenue" and amount <= 0)
    ):
        return None, "invalid_amount_or_unit"
    if row["scope"] != entity.get("scope"):
        return None, "parent_brand_scope_mismatch"
    try:
        start, end = (
            calendar_date(row["period_start"]),
            calendar_date(row["period_end"]),
        )
    except (ValueError, TypeError):
        return None, "invalid_source_period_boundary"
    if start > end or (role != "baseline" and cutoff and end > cutoff.date()):
        return None, "invalid_or_future_actual_period"
    row.update(
        amount=amount,
        unit_multiplier=unit,
        period_start=start,
        period_end=end,
        analysis_id=analysis_id,
        entity_id=entity["entity_id"],
        role=role,
        historical_status="eligible",
        evidence=review["evidence"],
    )
    return row, "available"


def comparable(periods: list[Row]) -> bool:
    if len(periods) != 3:
        return False
    signatures = {
        (r["scope"], r["currency"], r["unit_multiplier"], r["period_type"])
        for r in periods
    }
    if len(signatures) != 1 or periods[0]["period_type"] not in {
        "annual",
        "quarter",
        "half_year",
    }:
        return False  # cumulative/YTD periods cannot stand in for discrete quarters.
    lengths = [(r["period_end"] - r["period_start"]).days + 1 for r in periods]
    bounds = {"annual": (350, 380), "quarter": (75, 105), "half_year": (170, 195)}
    lo, hi = bounds[periods[0]["period_type"]]
    if (
        not all(lo <= length <= hi for length in lengths)
        or max(lengths) - min(lengths) > 10
    ):
        return False
    for prior, current in zip(periods, periods[1:], strict=False):
        if not 350 <= (current["period_end"] - prior["period_end"]).days <= 380:
            return False
        if current["period_start"] <= prior["period_end"]:
            return False
    return True


def growth(current: float, prior: float) -> float:
    """Canonical rates are fractions; scoring explicitly converts to percent/pp."""
    return current / prior - 1


def series(
    inputs: Inputs,
    snapshot: Snapshot,
    analysis: Row,
    entity: Row,
    cutoff: datetime | None,
) -> tuple[list[Row], list[str]]:
    periods, reasons = [], []
    for role in ("oldest", "earlier", "latest"):
        row, status = select(
            inputs, snapshot, analysis["analysis_id"], entity, role, "revenue", cutoff
        )
        if row:
            periods.append(row)
        else:
            reasons.append(f"{entity['entity_id']}.{role}:{status}")
    if len(periods) == 3 and not comparable(periods):
        reasons.append(f"{entity['entity_id']}:noncomparable_financial_periods")
    return periods, reasons
