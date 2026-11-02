"""Select the dossier's explicit periods, never the latest/forecast quarter."""

from .financial import comparable
from .issuer_measurements import matches_subject
from .models import (
    Inputs,
    Row,
    Snapshot,
    calendar_date,
    fingerprint,
    instant,
    number,
    truth,
)


def annual_from_quarters(rows: list[Row], start, end) -> Row | None:
    """Only four source-verified, discrete, gapless quarters. No fiscal inference."""
    buckets: dict[tuple, list[Row]] = {}
    for row in rows:
        if row.get("period_boundaries_verified") is False:
            continue
        buckets.setdefault((row["period_start"], row["period_end"]), []).append(row)
    if len(buckets) != 4:
        return None
    selected = []
    for candidates in buckets.values():
        if (
            len(
                {
                    (r["amount"], r["currency"], r["unit_multiplier"], r["scope"])
                    for r in candidates
                }
            )
            != 1
        ):
            return None
        selected.append(sorted(candidates, key=lambda r: str(r["source_row_id"]))[0])
    selected.sort(key=lambda r: r["period_start"])
    if selected[0]["period_start"] != start or selected[-1]["period_end"] != end:
        return None
    if any(
        (b["period_start"] - a["period_end"]).days != 1
        for a, b in zip(selected, selected[1:], strict=False)
    ):
        return None
    if len({(r["currency"], r["unit_multiplier"], r["scope"]) for r in selected}) != 1:
        return None
    return {
        **selected[0],
        "period_start": start,
        "period_end": end,
        "period_type": "annual",
        "amount": sum(r["amount"] for r in selected),
        "source_relation": "fmi.verified_quarter_aggregation",
        "source_row_id": fingerprint([r["source_row_id"] for r in selected]),
        "source_classification": "aggregated_reported_discrete_quarters",
        "underlying_candidates": selected,
    }


def source_subject(entity: Row, analysis: Row, entities: list[Row]) -> Row:
    """Only an explicit dossier source mapping, never an automatic fallback."""
    spec = (
        analysis["dossier"]
        .get("financial", {})
        .get("entities", {})
        .get(entity["entity_id"], {})
    )
    source_id = spec.get("source_entity_id")
    if not source_id:
        return entity
    source = next(e for e in entities if e["entity_id"] == source_id)
    return {
        **entity,
        **{k: source.get(k) for k in ("light_code", "ticker", "shared_symbol")},
        "financial_subject": spec.get("subject"),
        "scope": spec.get("scope"),
        "proxy": source_id != entity["entity_id"],
        "proxy_label": (
            f"Dossier financial proxy: {spec.get('subject')}; "
            f"NOT standalone {entity['name']} revenue"
        ),
    }


def series(
    inputs: Inputs, entity: Row, snapshot: Snapshot, analysis: Row
) -> tuple[list[Row], list[str]]:
    spec = (
        analysis["dossier"]
        .get("financial", {})
        .get("entities", {})
        .get(entity["entity_id"], {})
    )
    if not spec:
        return [], [
            f"financial:{entity['entity_id']}:missing_dossier_period_definition"
        ]
    if (
        analysis["dossier"].get("financial", {}).get("growth_basis")
        == "published_comparable_growth"
    ):
        return [], [
            f"financial:{entity['entity_id']}:published_comparable_growth_source_required_not_nominal_revenue"
        ]
    entity = source_subject(entity, analysis, inputs.entities)
    cutoff = instant(snapshot.metadata.get("extracted_at"))
    periods, reasons = [], []
    symbol = entity.get("shared_symbol") or entity.get("ticker")
    for role in ("oldest", "earlier", "latest"):
        requested = spec.get("periods", {}).get(role, {})
        native_year = requested.get(
            "alignment"
        ) == "native_fiscal_year" and requested.get("label")
        if (
            not all(requested.get(k) for k in ("start", "end", "type"))
            and not native_year
        ) or not spec.get("scope"):
            reasons.append(
                f"financial:{entity['entity_id']}:{role}:missing_dossier_dates_or_scope"
            )
            continue
        start = calendar_date(requested["start"]) if requested.get("start") else None
        end = calendar_date(requested["end"]) if requested.get("end") else None
        review = next(
            (
                r
                for r in inputs.financial_review
                if r["analysis_id"] == analysis["analysis_id"]
                and r["entity_id"] == entity["entity_id"]
                and r["role"] == role
                and truth(r.get("approved"))
                and r.get("evidence")
            ),
            {},
        )
        candidates, quarters = [], []
        for raw in snapshot.financials:
            if raw.get("kind") != "actual" or raw.get("metric") != spec.get(
                "metric", "revenue"
            ):
                continue
            available = instant(raw.get("available_at"))
            captured = instant(raw.get("crawled_at"))
            if cutoff is None or any(
                stamp and stamp > cutoff for stamp in (available, captured)
            ):
                continue
            issuer_measurement = matches_subject(raw, spec)
            shared = str(raw.get("source_relation", "")).startswith(
                ("normalized.", "denormalized.")
            )
            if not issuer_measurement and (
                (shared and (not symbol or raw.get("symbol") != symbol))
                or (
                    not shared
                    and (
                        not entity.get("light_code")
                        or raw.get("company_code") != entity["light_code"]
                    )
                )
            ):
                continue
            selected = raw.get("source_row_id") == review.get("source_row_id")
            if review.get("source_row_id") and not selected:
                continue
            row = {
                **raw,
                **{
                    k: review[k]
                    for k in (
                        "period_start",
                        "period_end",
                        "period_type",
                        "scope",
                        "currency",
                        "unit_multiplier",
                    )
                    if selected
                    and raw.get(k) in (None, "")
                    and review.get(k) not in (None, "")
                },
            }
            if issuer_measurement:
                row["scope"] = spec["scope"]  # Explicit parent-segment label only.
            if not all(
                row.get(k)
                for k in (
                    "period_start",
                    "period_end",
                    "period_type",
                    "scope",
                    "currency",
                    "unit_multiplier",
                    "source_row_id",
                )
            ):
                continue
            native_start, native_end = (
                calendar_date(row["period_start"]),
                calendar_date(row["period_end"]),
            )
            aligned = (native_start, native_end) == (start, end)
            if native_year and (start is None or end is None):
                aligned = requested["label"] == (
                    row.get("fiscal_year_label")
                    or (row.get("period_label") if not shared else None)
                )
            if (
                start
                and end
                and requested.get("alignment") == "calendar_selling_window_proxy"
            ):
                aligned = (
                    abs((native_start - start).days) <= 14
                    and abs((native_end - end).days) <= 14
                )
            if (
                native_start > native_end
                or cutoff is None
                or native_end > cutoff.date()
            ):
                continue
            partial = bool(
                start
                and end
                and requested["type"] == "annual"
                and row["period_type"] == "quarter"
                and analysis["dossier"]["financial"].get("aggregation")
                == "sum_verified_discrete_quarters"
                and start <= native_start <= native_end <= end
                and 75 <= (native_end - native_start).days <= 105
            )
            if row["scope"] != spec["scope"] or (
                not partial and (not aligned or row["period_type"] != requested["type"])
            ):
                continue
            if not selected and row.get("source_classification") not in {
                "reported",
                "reported_actual",
                "reported_annual",
            }:
                continue
            amount, unit = number(row.get("amount")), number(row.get("unit_multiplier"))
            if amount is None or amount <= 0 or unit is None or unit <= 0:
                continue
            (quarters if partial else candidates).append(
                {
                    **row,
                    "amount": amount,
                    "unit_multiplier": unit,
                    "period_start": native_start,
                    "period_end": native_end,
                    "period_label": requested.get("label") or f"{start}/{end}",
                    "role": role,
                    "entity_id": entity["entity_id"],
                    "analysis_id": analysis["analysis_id"],
                    "financial_subject": spec.get("subject"),
                    "historical_status": "dossier_current_source_not_historical_replay",
                    "period_alignment": requested.get(
                        "alignment", "exact_dossier_boundaries"
                    ),
                }
            )
        if not candidates and quarters:
            annual = annual_from_quarters(quarters, start, end)
            if annual:
                candidates.append(annual)
        signatures = {
            (r["amount"], r["currency"], r["unit_multiplier"], r["scope"])
            for r in candidates
        }
        if len(signatures) != 1:
            reasons.append(
                f"financial:{entity['entity_id']}:{role}:"
                + (
                    "conflicting_dossier_measurements"
                    if signatures
                    else f"missing_verified_{spec.get('scope')}_{start}_{end}"
                )
            )
        else:
            periods.append(
                min(
                    candidates,
                    key=lambda r: (
                        r.get("period_boundaries_verified") is not True,
                        str(r["source_row_id"]),
                    ),
                )
            )
    if len({(r["currency"], r["unit_multiplier"], r["scope"]) for r in periods}) > 1:
        reasons.append(
            f"financial:{entity['entity_id']}:noncomparable_dossier_currency_units_scope"
        )
    if len(periods) == 3 and not comparable(periods):
        reasons.append(f"financial:{entity['entity_id']}:noncomparable_dossier_periods")
    return periods, reasons


def trend(earlier: float, latest: float, settings: Row, policy) -> tuple[float, str]:
    from .scoring import trend as controlled_trend

    if settings.get("basis") == "assumed":
        return float(settings["assumed_score"]), "dossier_assumed_not_measured"
    if settings.get("rule") == "improvement_sign":
        change = latest - earlier
        if change > policy.trend_change_boundary_pp:
            return (80, "strong") if latest >= 0 else (70, "up_and_coming")
        return (
            (30, "declining")
            if change < -policy.trend_change_boundary_pp
            else (50, "stable")
        )
    return controlled_trend(earlier, latest, policy)
