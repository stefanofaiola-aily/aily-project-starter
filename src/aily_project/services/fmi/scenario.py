"""Current-source presentation simulation, kept separate from strict replay gates.

No approvals, publication vintages, currency conversions or source amounts are
invented. Native quarterly observations are period proxies, not verified reports.
"""

from calendar import monthrange
from datetime import date, timedelta
from statistics import median

from . import financial, social
from .models import (
    FMIResult,
    Inputs,
    Row,
    Snapshot,
    calendar_date,
    fingerprint,
    instant,
    number,
    truth,
)
from .policy import Policy

ACTUAL = "light.light_financial_statements_actuals"
FORECAST = "ai.light_financial_statements_forecast"
CONSOLIDATED = "normalized.v_finance_financial_statements"


def year_ago(day: date, years: int = 1) -> date:
    year = day.year - years
    return day.replace(year=year, day=min(day.day, monthrange(year, day.month)[1]))


def quarter_start_proxy(end: date) -> date:
    """Three-month proxy only; do not claim source-verified retail boundaries."""
    month_index = end.year * 12 + end.month - 1 - 3
    year, month = divmod(month_index, 12)
    month += 1
    return date(year, month, min(end.day, monthrange(year, month)[1])) + timedelta(
        days=1
    )


def native_candidates(
    rows: list[Row], snapshot: Snapshot, forecast: bool, metric: str
) -> list[tuple[Row, date]]:
    extracted = instant(snapshot.metadata.get("extracted_at"))
    if extracted is None:
        return []
    candidates = []
    for row in rows:
        if (
            row.get("metric") != metric
            or row.get("kind") != ("forecast" if forecast else "actual")
            or not row.get("source_row_id")
            or number(row.get("amount")) is None
            or str(row.get("quarter") or row.get("period") or "").upper()
            not in {"Q1", "Q2", "Q3", "Q4"}
        ):
            continue
        try:
            end = calendar_date(
                row.get("reported_date") or row.get("date") or row.get("period_end")
            )
        except (ValueError, TypeError):
            continue
        if (forecast and end > extracted.date()) or (
            not forecast and end <= extracted.date()
        ):
            candidates.append((row, end))
    return candidates


def subject_rows(entity: Row, snapshot: Snapshot) -> tuple[list[Row], str]:
    """Resolve only configured subjects; never use fuzzy aliases as measurements."""
    if truth(entity.get("proxy")) and not (
        financial.identity_ready(entity)
        or (
            truth(entity.get("proxy_authorized"))
            and entity.get("proxy_label")
            and entity.get("scope")
            and entity.get("evidence")
        )
    ):
        return [], "unreviewed_parent_or_group_proxy"
    code = entity.get("light_code")
    registry = [r for r in snapshot.registry if code and r.get("company_code") == code]
    if code and len(registry) != 1:
        return [], "missing_or_ambiguous_light_registry_mapping"
    if registry:
        ticker = registry[0].get("company_ticker")
        if ticker and entity.get("ticker") and ticker != entity["ticker"]:
            return [], "configured_ticker_conflicts_with_light_registry"
    symbol = entity.get("shared_symbol") or entity.get("ticker")
    rows = [
        r
        for r in snapshot.financials
        if (
            code
            and r.get("company_code") == code
            and r.get("source_relation") in {ACTUAL, FORECAST}
        )
        or (
            symbol
            and r.get("symbol") == symbol
            and r.get("source_relation") == CONSOLIDATED
        )
    ]
    return (
        rows,
        "configured_light_subject"
        if registry
        else "configured_shared_symbol_not_registry_verified",
    )


def subject_keys(entity: Row) -> set[tuple[str, str]]:
    """Keep code and ticker namespaces distinct while detecting shared subjects."""
    return {
        ("code" if k == "light_code" else "symbol", str(entity[k]))
        for k in ("light_code", "ticker", "shared_symbol")
        if entity.get(k)
    } or {("entity", str(entity["entity_id"]))}


def select_period(
    entity: Row,
    snapshot: Snapshot,
    end: date,
    role: str,
    analysis_id: str,
    tolerance: int,
    metric: str = "revenue",
    native_quarter: str | None = None,
) -> tuple[Row | None, str]:
    rows, status = subject_rows(entity, snapshot)
    if not rows:
        return None, status if status.startswith(
            ("missing", "unreviewed", "configured_ticker")
        ) else "no_financial_rows_for_configured_subject"
    forecast = role == "baseline"
    relations = [FORECAST] if forecast else [ACTUAL, CONSOLIDATED]
    candidates = [
        (row, native_end)
        for row, native_end in native_candidates(rows, snapshot, forecast, metric)
        if abs((native_end - end).days) <= tolerance
        and row.get("source_relation") in relations
        and (
            native_quarter is None
            or str(row.get("quarter") or row.get("period")).upper() == native_quarter
        )
    ]
    if not candidates:
        return None, f"missing_native_quarter_{metric}_ending_near_{end}"
    rank = min(relations.index(r["source_relation"]) for r, _ in candidates)
    preferred = [
        (r, e) for r, e in candidates if relations.index(r["source_relation"]) == rank
    ]
    distance = min(abs((e - end).days) for _, e in preferred)
    preferred = [(r, e) for r, e in preferred if abs((e - end).days) == distance]
    signatures = {
        (e, number(r["amount"]), r.get("currency"), r.get("unit_multiplier"))
        for r, e in preferred
    }
    if len(signatures) != 1:
        return None, f"conflicting_native_quarter_{metric}_{end}"
    row, native_end = sorted(preferred, key=lambda pair: str(pair[0]["source_row_id"]))[
        0
    ]
    matching = [
        r
        for r, e in candidates
        if e == native_end and r["source_relation"] == CONSOLIDATED
    ]
    if matching and any(number(r["amount"]) != number(row["amount"]) for r in matching):
        return None, f"light_shared_amount_conflict_{metric}_{end}"
    currencies = {r["currency"] for r in [row, *matching] if r.get("currency")}
    registry_currency = next(
        (
            r.get("currency")
            for r in snapshot.registry
            if r.get("company_code") == entity.get("light_code")
        ),
        None,
    )
    history_currencies = {
        r.get("currency")
        for r, _ in native_candidates(rows, snapshot, False, metric)
        if r.get("currency")
    }
    history_currency = (
        next(iter(history_currencies)) if len(history_currencies) == 1 else None
    )
    if not currencies and history_currency:
        currencies.add(history_currency)
    if registry_currency and not currencies:
        currencies.add(registry_currency)
    units = {
        r["unit_multiplier"]
        for r in [row, *matching]
        if r.get("unit_multiplier") is not None
    }
    if len(currencies) > 1 or len(units) > 1:
        return None, f"source_currency_or_unit_conflict_{metric}_{end}"
    # Calendar proxy boundaries are derived, never labelled source-verified.
    start = quarter_start_proxy(native_end)
    return {
        **row,
        "entity_id": entity["entity_id"],
        "analysis_id": analysis_id,
        "role": role,
        "amount": number(row["amount"]),
        "period_end": native_end,
        "period_start": start,
        "period_type": "quarter",
        "scope": entity.get("scope"),
        "currency": next(iter(currencies), None),
        "currency_basis": "source_observation"
        if currencies
        and (row.get("currency") or any(r.get("currency") for r in matching))
        else "same_subject_source_history_assumption"
        if history_currency
        else "light_registry_denomination_assumption"
        if registry_currency
        else "unknown",
        "unit_multiplier": next(iter(units), None),
        "source_classification": (
            matching[0].get("source_classification")
            if matching
            else row.get("source_classification")
        ),
        "underlying_candidates": matching,
        "selection_basis": status,
        "period_alignment": "exact_end_date_native_quarter_proxy"
        if native_end == end
        else "fiscal_end_date_native_quarter_proxy",
        "period_boundaries_verified": False,
        "historical_status": "current_source_simulation_not_replay",
        "vintage_verified": False,
        "available_at": None,
    }, "available_native_period_proxy"


def series(
    entity: Row, snapshot: Snapshot, analysis: Row, tolerance: int
) -> tuple[list[Row], list[str]]:
    end = calendar_date(analysis["forecast_target_end"])
    latest_available = analysis.get("financial_basis") == "latest_available"
    native_quarter = None
    if latest_available:
        rows, status = subject_rows(entity, snapshot)
        candidates = native_candidates(rows, snapshot, False, "revenue")
        if not candidates:
            return [], [f"financial:latest:{status}:no_eligible_actual_quarter"]
        end = max(day for _, day in candidates)
        latest, status = select_period(
            entity, snapshot, end, "latest", analysis["analysis_id"], 0
        )
        if latest is None:
            return [], [f"financial:latest:{status}"]
        native_quarter = str(latest.get("quarter") or latest.get("period")).upper()
    periods, reasons = [], []
    for role, offset in (
        (("oldest", 2), ("earlier", 1), ("latest", 0))
        if latest_available
        else (("oldest", 3), ("earlier", 2), ("latest", 1))
    ):
        row, status = select_period(
            entity,
            snapshot,
            year_ago(end, offset),
            role,
            analysis["analysis_id"],
            0 if latest_available and offset == 0 else tolerance,
            native_quarter=native_quarter,
        )
        if row is None or row["amount"] is None or row["amount"] <= 0:
            reasons.append(
                f"financial:{role}:{status if row is None else 'nonpositive_revenue'}"
            )
        else:
            periods.append(row)
    if len({r["source_relation"] for r in periods}) > 1 and not entity.get(
        "financial_comparability_evidence"
    ):
        reasons.append("financial:mixed_light_shared_series_requires_review")
    for key in ("currency", "unit_multiplier"):
        if len({r[key] for r in periods if r.get(key) is not None}) > 1:
            reasons.append(f"financial:noncomparable_{key}")
    return periods, reasons


def financial_subject(
    entity: Row, snapshot: Snapshot, analysis: Row, policy: Policy
) -> Row:
    """Presentation-only evidenced parent fallback; keep the brand's social identity.

    Prefer a complete brand series unless the input explicitly prefers its parent.
    Never release this route through strict replay.
    Forecast and peer selection resolve the same financial subject as the score.
    """
    parent = entity.get("parent", {})
    if (
        analysis.get("calculation_mode") != "presentation"
        or not truth(parent.get("authorized"))
        or not parent.get("evidence")
    ):
        return entity
    _, missing = series(
        entity, snapshot, analysis, policy.scenario_quarter_tolerance_days
    )
    if not missing and not truth(parent.get("prefer")):
        return entity
    candidate = {
        **entity,
        **{k: parent.get(k) for k in ("light_code", "ticker", "shared_symbol")},
        "financial_subject": parent["name"],
        "scope": "parent_group",
        "proxy": True,
        "proxy_authorized": True,
        "evidence": parent["evidence"],
        "proxy_label": f"{parent['name']} group revenue/forecast proxy for "
        f"{entity['name']}; NOT standalone brand amounts",
    }
    # Even if the parent is incomplete, retain its available drivers and reasons.
    return candidate


def raw_scenario(
    inputs: Inputs,
    snapshot: Snapshot,
    analysis: Row,
    entity: Row,
    entities: dict[str, Row],
    policy: Policy,
    run_id: str,
) -> FMIResult:
    from .scoring import _growth, complete_score, trend

    original_entity = entity
    dossier = analysis.get("calculation_mode") == "dossier"
    if dossier:
        from .dossier_selection import source_subject

        entity = source_subject(entity, analysis, inputs.entities)
    else:
        entity = financial_subject(entity, snapshot, analysis, policy)
    result = FMIResult(entity["entity_id"], analysis["analysis_id"])
    v = result.values
    v.update(
        {
            k: entity.get(k)
            for k in (
                "name",
                "light_code",
                "ticker",
                "shared_symbol",
                "financial_subject",
                "scope",
                "proxy_label",
                "handle",
                "profile_id",
                "event_category",
                "event_invited",
                "fmi_required",
            )
        }
    )
    v.update(
        {
            k: analysis.get(k)
            for k in (
                "route",
                "collection",
                "show_date",
                "timezone",
                "forecast_target_label",
                "forecast_target_start",
                "forecast_target_end",
            )
        }
    )
    cutoff = instant(snapshot.metadata.get("extracted_at"))
    configured_financials, identity_basis = subject_rows(entity, snapshot)
    captures = [
        r
        for r in snapshot.posts
        if entity.get("handle")
        and str(r.get("profile_username", "")).lower()
        == str(entity["handle"]).lower().lstrip("@")
    ]
    v.update(
        financial_candidate_count=len(configured_financials),
        social_capture_count=len(captures),
        identity_status=identity_basis,
        source_query_coverage_status="financial_candidates_present"
        if configured_financials
        else "no_configured_subject_financial_rows",
        financial_coverage_status="native_period_candidates_not_verified_reports"
        if configured_financials
        else "no_configured_subject_financial_rows",
        social_history_status="current_capture_archive_not_historical_replay"
        if captures
        else "no_matching_instagram_captures",
    )
    v.update(
        entity_id=entity["entity_id"],
        proxy=truth(entity.get("proxy")),
        run_id=run_id,
        policy_id=policy.version,
        policy_hash=fingerprint(policy.model_dump()),
        headline_selection=truth(analysis.get("selected")),
        calculation_mode="presentation",
        release_status="presentation_simulation_not_reviewed_replay",
        historical_status="current_source_simulation_not_replay",
        scenario_as_of=cutoff,
        cutoff=cutoff,
        signal_window_cutoff=analysis.get("cutoff"),
        data_extracted_at=cutoff,
        identity_status="configured_not_human_reviewed",
        analysis_review_status="simulation_not_human_reviewed",
        ir_weight=policy.ir_weight,
        social_weight=policy.social_weight,
        trend_weight=policy.trend_weight,
        scenario_quarter_tolerance_days=policy.scenario_quarter_tolerance_days,
        scenario_forecast_tolerance_days=policy.scenario_forecast_tolerance_days,
        financial_basis=analysis.get("financial_basis", "target_season"),
        revenue_alignment_status="same_season_native_quarters_before_forecast",
        financial_selection_basis="exact_configured_subject_and_end_date_not_fiscal_label",
        financial_unit_status="source_native_constant_scale_assumption_no_conversion",
        financial_scope_status="configured_subject_not_verified_standalone_scope",
        forecast_vintage_status="current_snapshot_no_verified_publication_vintage",
    )
    v.update(
        parent_name=original_entity.get("parent", {}).get("name"),
        parent_mapping_evidence=original_entity.get("parent", {}).get("evidence"),
        parent_fallback_status="used_authorized_parent_proxy"
        if entity is not original_entity
        else "brand_series_retained"
        if original_entity.get("parent")
        else "no_evidenced_parent_configured",
    )
    if cutoff is None or (not dossier and not analysis.get("forecast_target_end")):
        result.gaps.append("simulation:missing_extraction_time_or_forecast_target")
        complete_score(result)
        return result
    end = calendar_date(analysis.get("forecast_target_end") or cutoff.date())
    start = date(end.year, end.month - 2, 1) if end.month in {3, 6, 9, 12} else None
    if not dossier and (
        start is None
        or end.day != monthrange(end.year, end.month)[1]
        or not analysis.get("forecast_target_start")
        or calendar_date(analysis["forecast_target_start"]) != start
    ):
        result.gaps.append("simulation:calendar_quarter_target_required")
        complete_score(result)
        return result

    def score_series(subject: Row) -> tuple[list[Row], list[str]]:
        if dossier:
            from .dossier_selection import series as dossier_series

            return dossier_series(inputs, subject, snapshot, analysis)
        return series(
            subject, snapshot, analysis, policy.scenario_quarter_tolerance_days
        )

    periods, reasons = score_series(entity)
    if dossier:
        definition = (
            analysis["dossier"]
            .get("financial", {})
            .get("entities", {})
            .get(entity["entity_id"], {})
        )
        v.update(
            calculation_mode="dossier",
            release_status="dossier_defined_current_source_calculation",
            historical_status="retrospective_not_point_in_time_replay",
            analysis_review_status="business_dossier_parameters",
            revenue_alignment_status="explicit_dossier_periods_independent_of_forecast",
            financial_selection_basis="dossier_dates_scope_metric_no_latest_fallback",
            financial_scope_status="source_scope_matches_dossier"
            if periods and not reasons
            else "source_scope_must_match_dossier",
            financial_unit_status="verified_selected_source_units"
            if periods and not reasons
            else "verified_source_units_required",
            comparability_status="dossier_defined_periods_and_scopes",
            financial_coverage_status="verified_dossier_measurements"
            if periods and not reasons
            else "missing_verified_dossier_measurements",
            parent_fallback_status="explicit_dossier_source_subject"
            if entity is not original_entity
            else "dossier_brand_subject",
            dossier_source=analysis["dossier"].get("source"),
            dossier_parameter_status=analysis["dossier"].get("status"),
            headline_method=analysis.get("headline_method", "dossier_reference"),
            dossier_score_basis=analysis["dossier"].get("score_basis"),
            dossier_headline_replication_status="original_reference_cohort_unavailable"
            if analysis["dossier"].get("score_basis") == "percentile"
            else "current_measurements_not_frozen_reference_values",
            financial_subject=definition.get("subject"),
            scope=definition.get("scope"),
            trend_basis=analysis["dossier"].get("trend", {}).get("basis"),
            trend_comparison=analysis["dossier"].get("trend", {}).get("comparison"),
        )
        if (
            analysis["dossier"].get("score_basis") == "percentile"
            and analysis.get("headline_method", "dossier_reference")
            != "weighted_components"
        ):
            result.gaps.append(
                "dossier:percentile_normalization_requires_original_reference_cohort"
            )
    result.financial_periods.extend(periods)
    result.gaps.extend(reasons)
    if analysis.get("financial_basis") == "latest_available":
        v.update(
            revenue_alignment_status="latest_native_actual_and_same_season_year_ago_quarters",
            financial_selection_basis="latest_available_actual_by_native_end_date",
            comparability_status="each_subject_latest_native_quarter_peer_periods_may_differ",
        )
        latest_row = next((r for r in periods if r["role"] == "latest"), None)
        if latest_row:
            age = (cutoff.date() - latest_row["period_end"]).days
            v.update(
                latest_actual_age_days=age,
                financial_freshness_status="older_than_180_days"
                if age > 180
                else "within_180_days",
            )
    for row in periods:
        role = row["role"]
        for source, dest in (
            ("amount", "revenue"),
            ("period_label", "period_label"),
            ("period_start", "period_start"),
            ("period_end", "period_end"),
            ("source_classification", "source_classification"),
            ("source_row_id", "source_row_id"),
            ("source_relation", "source_relation"),
            ("source_url", "source_url"),
            ("currency", "currency"),
            ("unit_multiplier", "unit_multiplier"),
        ):
            v[f"{role}_{dest}"] = row.get(source)
        v.update(currency=row["currency"], unit_multiplier=row["unit_multiplier"])
        v["financial_currency_status"] = (
            "light_registry_denomination_assumed_not_verified_reporting_currency"
            if any(
                r.get("currency_basis") == "light_registry_denomination_assumption"
                for r in periods
            )
            else "same_subject_source_history_assumption"
            if any(
                r.get("currency_basis") == "same_subject_source_history_assumption"
                for r in periods
            )
            else "source_currency_or_unknown"
        )
        for metric in ("cost_of_revenue", "gross_profit", "ebitda"):
            context, _ = select_period(
                entity,
                snapshot,
                row["period_end"],
                role,
                analysis["analysis_id"],
                0,
                metric,
            )
            if dossier and context:
                native_context = next(
                    (
                        r
                        for r in snapshot.financials
                        if r.get("source_row_id") == context["source_row_id"]
                        and r.get("metric") == metric
                    ),
                    {},
                )
                if any(
                    native_context.get(k) != row.get(k)
                    for k in ("scope", "currency", "unit_multiplier")
                ):
                    context = None
            if context and all(
                context[k] == row[k]
                for k in (
                    "source_relation",
                    "scope",
                    "currency",
                    "unit_multiplier",
                    "period_start",
                    "period_end",
                )
            ):
                v[f"{role}_{metric}"] = context["amount"]
                v[f"{role}_{metric}_margin"] = context["amount"] / row["amount"]
                result.financial_periods.append(context)
    if not reasons:
        v.update(
            earlier_growth=_growth(periods, "oldest", "earlier"),
            latest_growth=_growth(periods, "earlier", "latest"),
        )
    assigned = [p for p in inputs.peers if p["analysis_id"] == analysis["analysis_id"]]
    approved = [p for p in assigned if truth(p.get("approved"))]
    v.update(
        approved_peer_count=len(approved),
        approved_peer_names="; ".join(
            entities[p["peer_entity_id"]]["name"] for p in approved
        ),
        peer_review_status="dossier_defined_usable_peer_subset"
        if dossier
        else "assigned_usable_subset_not_approved",
        comparability_status=v.get(
            "comparability_status", "calendar_end_alignment_source_native_assumptions"
        ),
    )
    used, seen = [], subject_keys(entity)
    for peer in assigned:
        if dossier:
            subject = source_subject(
                entities[peer["peer_entity_id"]], analysis, inputs.entities
            )
        else:
            subject = financial_subject(
                entities[peer["peer_entity_id"]], snapshot, analysis, policy
            )
        keys = subject_keys(subject)
        selected, missing = score_series(subject)
        if keys & seen:
            missing.append("duplicate_or_self_financial_subject")
        earlier, latest = (
            _growth(selected, "oldest", "earlier"),
            _growth(selected, "earlier", "latest"),
        )
        if earlier is None or latest is None:
            missing.append("missing_comparable_three_quarter_series")
        diagnostic = {
            **peer,
            "peer_name": subject["name"],
            "financial_subject": subject.get("financial_subject"),
            "proxy_label": subject.get("proxy_label"),
            "earlier_growth": earlier,
            "latest_growth": latest,
            "status": "excluded"
            if missing
            else "dossier_periods_used"
            if dossier
            else "simulation_used",
            "missing_reasons": "; ".join(missing),
            "pair_raw_fmi": None,
            **{
                f"{r['role']}_{key}": r.get(key)
                for r in selected
                for key in ("period_label", "period_end")
            },
        }
        result.peers.append(diagnostic)
        if not missing:
            seen.update(keys)
            used.append(diagnostic)
            result.financial_periods.extend(selected)
    v.update(
        used_peer_count=len(used),
        used_peer_names="; ".join(p["peer_name"] for p in used),
        used_peer_financial_subjects="; ".join(
            f"{p['peer_name']}: {p.get('financial_subject') or p['peer_name']}"
            for p in used
        ),
        peer_exclusion_reasons="; ".join(
            f"{p['peer_name']}: {p['missing_reasons']}"
            for p in result.peers
            if p["status"] == "excluded"
        ),
        used_peer_periods="; ".join(
            f"{p['peer_name']}: {p.get('oldest_period_label')} "
            f"ending {p.get('oldest_period_end')}, "
            f"{p.get('earlier_period_label')} ending {p.get('earlier_period_end')}, "
            f"{p.get('latest_period_label')} ending {p.get('latest_period_end')}"
            for p in used
        ),
        peer_calendar_alignment_status="different_native_end_dates"
        if any(p.get("latest_period_end") != v.get("latest_period_end") for p in used)
        else "same_native_end_dates"
        if used
        else "no_usable_peers",
    )
    if not used:
        result.gaps.append(
            "peers:no_assigned_peer_with_comparable_three_quarter_series"
        )
    for label in ("earlier", "latest"):
        if used:
            benchmark = median(p[f"{label}_growth"] for p in used)
            v[f"{label}_peer_median_growth"] = benchmark
            if v.get(f"{label}_growth") is not None:
                v[f"{label}_gap_pp"] = 100 * (v[f"{label}_growth"] - benchmark)
    if v.get("latest_gap_pp") is not None:
        v["ir_score"] = max(
            0, min(100, 50 + policy.ir_gap_multiplier * v["latest_gap_pp"])
        )
    if dossier and analysis["dossier"].get("trend", {}).get("basis") == "assumed":
        v["trend_score"] = analysis["dossier"]["trend"]["assumed_score"]
        v["trend_label"] = "dossier_assumed_not_measured"
    elif v.get("earlier_gap_pp") is not None and v.get("latest_gap_pp") is not None:
        v["trend_change_pp"] = v["latest_gap_pp"] - v["earlier_gap_pp"]
        if dossier:
            from .dossier_selection import trend as dossier_trend

            settings = analysis["dossier"].get("trend", {})
            earlier, latest = v["earlier_gap_pp"], v["latest_gap_pp"]
            if settings.get("basis") == "company_growth":
                earlier, latest = 100 * v["earlier_growth"], 100 * v["latest_growth"]
                v["trend_change_pp"] = latest - earlier
            v["trend_score"], v["trend_label"] = dossier_trend(
                earlier, latest, settings, policy
            )
        else:
            v["trend_score"], v["trend_label"] = trend(
                v["earlier_gap_pp"], v["latest_gap_pp"], policy
            )
    social_analysis = dict(analysis)
    if not dossier and not analysis.get("route"):
        assert start is not None
        social_analysis.update(
            route="period",
            timezone="UTC",
            current_start=start.replace(year=end.year - 1).isoformat(),
            current_end=end.replace(year=end.year - 1).isoformat(),
            baseline_start=start.replace(year=end.year - 2).isoformat(),
            baseline_end=end.replace(year=end.year - 2).isoformat(),
        )
        v.update(
            route="period",
            timezone="UTC",
            social_selection_basis="fallback_target_season_publication_windows_not_collection_specific",
        )
    else:
        v["social_selection_basis"] = (
            "explicit_dossier_windows_and_relevance_rule"
            if dossier
            else "document_dates_with_window_proxy_not_reviewed_collection_relevance"
        )
    values, posts, missing = social.calculate(
        inputs, snapshot, social_analysis, entity, cutoff, policy, simulation=True
    )
    v.update(values)
    result.social_posts = posts
    result.gaps.extend(missing)
    if v.get("ir_score") is None:
        result.gaps.append("ir:missing_brand_or_peer_quarter_growth")
    if v.get("trend_score") is None:
        result.gaps.append("trend:missing_earlier_and_latest_quarter_gaps")
    v["evidence_refs"] = "; ".join(
        str(x)
        for x in (
            entity.get("evidence"),
            analysis.get("evidence"),
            "Authenticated Light/shared measurements selected by dossier parameters; "
            "retrospective, not a point-in-time replay"
            if dossier
            else "Authenticated current Light/shared snapshot; native quarter "
            "proxies; no historical vintages",
        )
        if x
    )
    complete_score(result)
    return result


def forecast_scenario(
    result: FMIResult, inputs: Inputs, snapshot: Snapshot, analysis: Row, entity: Row
) -> None:
    from .scoring import apply_baseline

    v = result.values
    # Reuse the exact score subject; a standalone brand baseline is never paired
    # with growth derived from a parent's consolidated revenue.
    entity = {
        **entity,
        **{
            key: v[key]
            for key in (
                "light_code",
                "ticker",
                "shared_symbol",
                "financial_subject",
                "scope",
                "proxy",
                "proxy_label",
            )
            if key in v
        },
    }
    if v.get("parent_fallback_status") == "used_authorized_parent_proxy":
        entity.update(proxy_authorized=True, evidence=v.get("parent_mapping_evidence"))
    if analysis.get("calculation_mode") == "dossier" and truth(entity.get("proxy")):
        # Authorization is the explicit dossier source mapping, not an unrelated
        # optional presentation-mode parent preference. Do not create approvals.
        entity.update(
            proxy_authorized=bool(analysis["dossier"].get("source")),
            evidence=analysis["dossier"].get("source"),
        )
    if not analysis.get("forecast_target_end"):
        v.update(
            forecast_status="unavailable",
            forecast_missing_reason="missing_forecast_target",
        )
        return
    end = calendar_date(analysis["forecast_target_end"])
    baseline, status = select_period(
        entity,
        snapshot,
        end,
        "baseline",
        analysis["analysis_id"],
        int(
            v["scenario_forecast_tolerance_days"]
            if analysis.get("financial_basis") == "latest_available"
            else v["scenario_quarter_tolerance_days"]
        ),
    )
    cutoff = instant(snapshot.metadata.get("extracted_at"))
    if analysis.get("calculation_mode") == "dossier" and baseline:
        # select_period labels native proxies with configured scope. That label
        # is not proof the baseline actually measures retail/DTC or a segment.
        raw = next(
            (
                r
                for r in snapshot.financials
                if r.get("source_row_id") == baseline["source_row_id"]
                and r.get("metric") == "revenue"
            ),
            {},
        )
        review = next(
            (
                r
                for r in inputs.financial_review
                if r["analysis_id"] == analysis["analysis_id"]
                and r["entity_id"] == entity["entity_id"]
                and r["role"] == "baseline"
                and r.get("source_row_id") == baseline["source_row_id"]
                and truth(r.get("approved"))
                and r.get("evidence")
            ),
            {},
        )
        source_scope = raw.get("scope") or review.get("scope")
        if not source_scope or source_scope != v.get("scope"):
            baseline, status = (
                None,
                "dossier_forecast_scope_not_verified_or_incompatible",
            )
        elif (
            not (raw.get("currency") or review.get("currency"))
            or number(raw.get("unit_multiplier") or review.get("unit_multiplier"))
            is None
        ):
            baseline, status = None, "dossier_forecast_currency_or_units_not_verified"
    if baseline and (
        not cutoff or baseline["period_end"] <= cutoff.date() or baseline["amount"] <= 0
    ):
        baseline, status = None, "target_not_future_or_nonpositive_baseline"
    if baseline:
        for key in ("currency", "unit_multiplier"):
            if (
                v.get(key) is not None
                and baseline.get(key) is not None
                and v[key] != baseline[key]
            ):
                baseline, status = None, "forecast_actual_currency_or_units_conflict"
                break
    if not baseline:
        v.update(forecast_status="unavailable", forecast_missing_reason=status)
        return
    v.update(
        baseline_validation_status="current_native_quarter_proxy_no_verified_vintage_scope_or_scale",
        baseline_period_start=baseline["period_start"],
        baseline_period_end=baseline["period_end"],
        baseline_period_label=baseline.get("period_label"),
        baseline_fiscal_year=baseline.get("year"),
        baseline_native_quarter=baseline.get("quarter") or baseline.get("period"),
        forecast_selection_basis="nearest_future_native_quarter_to_requested_end"
        if analysis.get("financial_basis") == "latest_available"
        else "requested_end_date_native_quarter",
        forecast_calendar_alignment_status="matches_requested_end"
        if baseline["period_end"] == end
        else "native_fiscal_or_retail_period_differs_from_requested_calendar_target",
        forecast_target_end_difference_days=(baseline["period_end"] - end).days,
        baseline_source_row_id=baseline["source_row_id"],
        baseline_source_relation=baseline["source_relation"],
        baseline_currency=baseline.get("currency"),
        baseline_currency_basis=baseline.get("currency_basis"),
        baseline_unit_multiplier=baseline.get("unit_multiplier"),
        forecast_vintage=None,
    )
    prior, prior_status = select_period(
        entity,
        snapshot,
        year_ago(baseline["period_end"]),
        "prior_year_actual",
        analysis["analysis_id"],
        int(v["scenario_quarter_tolerance_days"]),
        native_quarter=str(baseline.get("quarter") or baseline.get("period")).upper(),
    )
    if analysis.get("calculation_mode") == "dossier" and prior:
        raw_prior = next(
            (
                r
                for r in snapshot.financials
                if r.get("source_row_id") == prior["source_row_id"]
            ),
            {},
        )
        if raw_prior.get("scope") != v.get("scope"):
            prior, prior_status = None, "dossier_forecast_prior_year_scope_not_verified"
    if prior and any(
        baseline.get(k) != prior.get(k)
        for k in ("currency", "unit_multiplier", "scope")
    ):
        prior, prior_status = (
            None,
            "forecast_prior_year_currency_units_or_scope_conflict",
        )
    if prior and prior["amount"] <= 0:
        prior, prior_status = None, "nonpositive_forecast_prior_year_actual"
    v.update(
        prior_year_actual_status=prior_status,
        prior_year_actual_period_label=prior.get("period_label") if prior else None,
        prior_year_actual_period_end=prior.get("period_end") if prior else None,
    )
    apply_baseline(result, baseline, prior)
