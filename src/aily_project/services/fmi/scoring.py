"""One controlled calculation path for notebooks, Excel and app records."""

import math
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from statistics import median

from . import financial, social
from .models import (
    FMIResult,
    Inputs,
    Row,
    Snapshot,
    fingerprint,
    instant,
    show_cutoff,
    truth,
)
from .policy import Policy


def trend(earlier_gap: float, latest_gap: float, policy: Policy) -> tuple[float, str]:
    change = latest_gap - earlier_gap
    if change > policy.trend_change_boundary_pp:
        return 70, "improving"
    if change < -policy.trend_change_boundary_pp:
        return 30, "declining"
    if min(earlier_gap, latest_gap) >= policy.sustained_gap_pp:
        return 80, "sustained_outperformance"
    return 50, "stable"


def classify(raw: float) -> str:
    return (
        "High"
        if raw >= 70
        else "Medium"
        if raw >= 60
        else "Neutral"
        if raw >= 40
        else "Low"
    )


def half_up(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def uplift(display: float, policy: Policy) -> float:
    if not 0 <= display <= 100:
        raise ValueError("Display score must be in 0–100")
    return (
        policy.uplift_max
        * math.expm1(policy.uplift_exponent * display / 100)
        / math.expm1(policy.uplift_exponent)
    )


def cutoff_for(analysis: Row) -> datetime | None:
    if analysis.get("route") == "show":
        if not analysis.get("show_date") or not analysis.get("timezone"):
            return None
        cutoff = show_cutoff(analysis["show_date"], analysis["timezone"])
        provided = instant(analysis.get("cutoff"))
        if analysis.get("cutoff") and provided != cutoff:
            raise ValueError(
                f"{analysis['analysis_id']}: explicit cutoff conflicts with show +37"
            )
        return cutoff
    if analysis.get("route") == "annual" and analysis.get("timezone"):
        return instant(analysis.get("cutoff"))
    return None


def _growth(periods: list[Row], left: str, right: str) -> float | None:
    index = {r["role"]: r for r in periods}
    if left not in index or right not in index:
        return None
    a, b = index[left], index[right]
    signatures = {
        (r["scope"], r["currency"], r["unit_multiplier"], r["period_type"])
        for r in (a, b)
    }
    if (
        len(signatures) != 1
        or not 350 <= (b["period_end"] - a["period_end"]).days <= 380
    ):
        return None
    if b["period_start"] <= a["period_end"]:
        return None
    bounds = {"annual": (350, 380), "quarter": (75, 105), "half_year": (170, 195)}
    lo, hi = bounds.get(a["period_type"], (1, 0))
    lengths = [(r["period_end"] - r["period_start"]).days + 1 for r in (a, b)]
    if not all(lo <= n <= hi for n in lengths) or abs(lengths[0] - lengths[1]) > 10:
        return None
    return financial.growth(b["amount"], a["amount"])


def raw_result(
    inputs: Inputs,
    snapshot: Snapshot,
    analysis: Row,
    entity: Row,
    entities: dict[str, Row],
    policy: Policy,
    run_id: str,
) -> FMIResult:
    result = FMIResult(entity["entity_id"], analysis["analysis_id"])
    cutoff = cutoff_for(analysis)
    v = result.values
    for column in (
        "name",
        "light_code",
        "ticker",
        "shared_symbol",
        "financial_subject",
        "scope",
        "proxy",
        "proxy_label",
        "handle",
        "profile_id",
    ):
        v[column] = entity.get(column)
    v["proxy"] = truth(entity.get("proxy"))
    v.update(
        entity_id=entity["entity_id"],
        run_id=run_id,
        policy_id=policy.version,
        policy_hash=fingerprint(policy.model_dump()),
        headline_selection=truth(analysis.get("selected")),
        cutoff=cutoff.isoformat() if cutoff else None,
        historical_status="strict_replay",
        ir_weight=policy.ir_weight,
        social_weight=policy.social_weight,
        trend_weight=policy.trend_weight,
    )
    for column in (
        "route",
        "collection",
        "show_date",
        "timezone",
        "forecast_target_label",
        "forecast_target_start",
        "forecast_target_end",
    ):
        v[column] = analysis.get(column)
    v["identity_status"] = (
        "reviewed" if financial.identity_ready(entity) else "review_required"
    )
    v["analysis_review_status"] = (
        "reviewed"
        if truth(analysis.get("reviewed")) and analysis.get("evidence")
        else "review_required"
    )
    financial_candidates = [
        r
        for r in snapshot.financials
        if r.get("symbol") in financial.symbols(entity)
        or (entity.get("light_code") and r.get("company_code") == entity["light_code"])
    ]
    v["financial_coverage_status"] = (
        "candidates_require_scope_and_vintage_review"
        if financial_candidates
        else "no_resolved_financial_candidates"
    )
    v["forecast_vintage_status"] = (
        "verified_candidate_requires_selection"
        if any(
            r.get("kind") == "forecast" and financial.eligible(r, cutoff)[0]
            for r in financial_candidates
        )
        else "missing_dated_verified_baseline_source"
    )
    source_posts = [
        r
        for r in snapshot.posts
        if entity.get("handle")
        and str(r.get("profile_username", "")).lower() == str(entity["handle"]).lower()
    ]
    retained = social.observations(source_posts, cutoff)[0] if cutoff else []
    v["social_history_status"] = (
        "missing_handle_or_cutoff"
        if not cutoff or not entity.get("handle")
        else "dated_captures_require_window_and_relevance_review"
        if retained
        else "no_eligible_timezone_qualified_capture"
    )
    if not financial.identity_ready(entity):
        result.gaps.append("identity:mapping_scope_or_evidence_unreviewed")
    if not truth(analysis.get("reviewed")) or not analysis.get("evidence"):
        result.gaps.append("analysis:review_or_evidence_required")
    if not cutoff:
        result.gaps.append("analysis:cutoff_route_or_timezone_required")
    periods, reasons = financial.series(inputs, snapshot, analysis, entity, cutoff)
    result.financial_periods.extend(periods)
    result.gaps.extend(reasons)
    for row in periods:
        role = row["role"]
        for src, dest in (
            ("amount", "revenue"),
            ("period_label", "period_label"),
            ("period_start", "period_start"),
            ("period_end", "period_end"),
            ("source_classification", "source_classification"),
        ):
            value = row.get(src)
            v[f"{role}_{dest}"] = (
                value.isoformat() if hasattr(value, "isoformat") else value
            )
        v.update(currency=row["currency"], unit_multiplier=row["unit_multiplier"])
        v[f"{role}_currency"] = row["currency"]
        v[f"{role}_unit_multiplier"] = row["unit_multiplier"]
        for metric in ("cost_of_revenue", "gross_profit", "ebitda"):
            context, _ = financial.select(
                inputs, snapshot, analysis["analysis_id"], entity, role, metric, cutoff
            )
            if context and all(
                context[k] == row[k]
                for k in (
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
    v["earlier_growth"] = _growth(periods, "oldest", "earlier")
    v["latest_growth"] = _growth(periods, "earlier", "latest")
    if analysis.get("route") == "annual" and any(
        r["period_type"] != "annual" for r in periods
    ):
        result.gaps.append("financial:annual_route_requires_annual_observations")
    approved = [
        p
        for p in inputs.peers
        if p["analysis_id"] == analysis["analysis_id"] and truth(p.get("approved"))
    ]
    v.update(
        approved_peer_count=len(approved),
        approved_peer_names="; ".join(
            str(entities[p["peer_entity_id"]]["name"]) for p in approved
        ),
    )
    all_peers: list[Row] = []
    v["peer_review_status"] = "approved_set" if approved else "no_approved_peer_set"
    for p in inputs.peers:
        if p["analysis_id"] != analysis["analysis_id"]:
            continue
        peer = entities[p["peer_entity_id"]]
        diagnostic = {
            **p,
            "peer_name": peer["name"],
            "status": "unreviewed",
            "pair_raw_fmi": None,
        }
        if truth(p.get("approved")):
            peer_periods, peer_reasons = financial.series(
                inputs, snapshot, analysis, peer, cutoff
            )
            result.financial_periods.extend(peer_periods)
            diagnostic.update(
                earlier_growth=_growth(peer_periods, "oldest", "earlier"),
                latest_growth=_growth(peer_periods, "earlier", "latest"),
            )
            if not truth(p.get("comparable")) or not p.get("evidence"):
                peer_reasons.append("peer_scope_or_calendar_comparability_unreviewed")
            diagnostic.update(
                status="available" if not peer_reasons else "unavailable",
                missing_reasons="; ".join(peer_reasons),
            )
            result.gaps.extend(f"peer:{p['peer_entity_id']}:{r}" for r in peer_reasons)
            all_peers.append(diagnostic)
        result.peers.append(diagnostic)
    same_peer_set = (
        bool(all_peers)
        and all(truth(p.get("comparable")) and p.get("evidence") for p in all_peers)
        and truth(analysis.get("financial_comparable"))
    )
    subjects = [entities[p["peer_entity_id"]] for p in approved]
    duplicate_subject = any(
        financial.symbols(a) & financial.symbols(b)
        or (a.get("light_code") and a.get("light_code") == b.get("light_code"))
        for i, a in enumerate(subjects)
        for b in [entity, *subjects[:i]]
    )
    if duplicate_subject:
        same_peer_set = False
        result.gaps.append("peers:duplicate_or_self_financial_subject_requires_review")
    v["comparability_status"] = "reviewed" if same_peer_set else "review_required"
    for label in ("earlier", "latest"):
        if same_peer_set and all(
            p.get(f"{label}_growth") is not None for p in all_peers
        ):
            peer_median = median(p[f"{label}_growth"] for p in all_peers)
            v[f"{label}_peer_median_growth"] = peer_median
            if v.get(f"{label}_growth") is not None:
                v[f"{label}_gap_pp"] = 100 * (v[f"{label}_growth"] - peer_median)
    if not approved:
        result.gaps.append("peers:no_approved_peer_set")
    if not same_peer_set:
        result.gaps.append("peers:comparability_review_required")
    latest_gap, earlier_gap = v.get("latest_gap_pp"), v.get("earlier_gap_pp")
    if latest_gap is not None:
        v["ir_score"] = max(0, min(100, 50 + policy.ir_gap_multiplier * latest_gap))
    if latest_gap is not None and earlier_gap is not None:
        v["trend_change_pp"] = latest_gap - earlier_gap
        v["trend_score"], v["trend_label"] = trend(earlier_gap, latest_gap, policy)
    social_values, posts, social_reasons = social.calculate(
        inputs, snapshot, analysis, entity, cutoff, policy
    )
    v.update(social_values)
    result.social_posts = posts
    result.gaps.extend(social_reasons)
    for component in ("ir", "social", "trend"):
        score = v.get(f"{component}_score")
        v[f"{component}_status"] = "available" if score is not None else "unavailable"
        v[f"{component}_contribution"] = (
            score * v[f"{component}_weight"] if score is not None else None
        )
    if not result.gaps and all(
        v.get(f"{c}_score") is not None for c in ("ir", "social", "trend")
    ):
        v["raw_fmi"] = sum(v[f"{c}_contribution"] for c in ("ir", "social", "trend"))
        v["raw_classification"] = classify(v["raw_fmi"])
        v["fmi_status"] = "available"
    else:
        v["fmi_status"] = "unavailable"
    v["historical_status"] = (
        "strict_inputs_eligible"
        if v["fmi_status"] == "available"
        else "strict_inputs_incomplete"
    )
    for p in all_peers:
        for label in ("earlier", "latest"):
            if (
                p.get(f"{label}_growth") is not None
                and v.get(f"{label}_growth") is not None
            ):
                p[f"{label}_gap_pp"] = 100 * (
                    v[f"{label}_growth"] - p[f"{label}_growth"]
                )
        if (
            p.get("status") == "available"
            and p.get("earlier_gap_pp") is not None
            and p.get("latest_gap_pp") is not None
            and v.get("social_score") is not None
        ):
            pair_trend, _ = trend(p["earlier_gap_pp"], p["latest_gap_pp"], policy)
            pair_ir = max(
                0, min(100, 50 + policy.ir_gap_multiplier * p["latest_gap_pp"])
            )
            p["pair_raw_fmi"] = (
                policy.ir_weight * pair_ir
                + policy.social_weight * v["social_score"]
                + policy.trend_weight * pair_trend
            )
    if v.get("ir_score") is None:
        result.gaps.append("ir:missing_eligible_latest_brand_or_peer_growth")
    if v.get("trend_score") is None:
        result.gaps.append("trend:missing_eligible_earlier_and_latest_gaps")
    v["evidence_refs"] = "; ".join(
        str(x) for x in (entity.get("evidence"), analysis.get("evidence")) if x
    )
    return result


def rescale(results: list[FMIResult], policy: Policy) -> Row:
    cohort = [
        r
        for r in results
        if r.values.get("fmi_status") == "available"
        and r.values.get("headline_selection")
        and r.values.get("raw_fmi") is not None
    ]
    raw = [float(r.values["raw_fmi"]) for r in cohort]
    lo, hi = (min(raw), max(raw)) if raw else (None, None)
    membership = sorted(str(r.analysis_id) for r in cohort)
    cohort_id = fingerprint(
        {
            "members": membership,
            "raw": sorted((r.analysis_id, r.values["raw_fmi"]) for r in cohort),
            "policy": policy.model_dump(),
        }
    )
    for r in results:
        r.values.update(
            cohort_id=cohort_id, cohort_min=lo, cohort_max=hi, cohort_count=len(cohort)
        )
        r.values["display_fmi"] = None
        r.values["uplift_fraction"] = None
    for r in cohort:
        assert lo is not None and hi is not None
        display = (
            policy.display_equal
            if lo == hi
            else policy.display_lower
            + (policy.display_upper - policy.display_lower)
            * (float(r.values["raw_fmi"]) - lo)
            / (hi - lo)
        )
        r.values["display_fmi"] = half_up(display)
        r.values["uplift_fraction"] = uplift(r.values["display_fmi"], policy)
    return {"cohort_id": cohort_id, "members": membership, "minimum": lo, "maximum": hi}


def forecast(
    result: FMIResult, inputs: Inputs, snapshot: Snapshot, analysis: Row, entity: Row
) -> None:
    v = result.values
    cutoff = cutoff_for(analysis)
    baseline, status = financial.select(
        inputs, snapshot, analysis["analysis_id"], entity, "baseline", "revenue", cutoff
    )
    from .models import calendar_date

    if baseline:
        checks = bool(cutoff) and baseline["period_start"] > cutoff.date()
        bounds = {"annual": (350, 380), "quarter": (75, 105), "half_year": (170, 195)}
        lo, hi = bounds.get(baseline["period_type"], (1, 0))
        checks = (
            checks
            and lo <= (baseline["period_end"] - baseline["period_start"]).days + 1 <= hi
        )
        checks = checks and truth(analysis.get("forecast_alignment_reviewed"))
        checks = checks and all(
            analysis.get(k)
            for k in (
                "forecast_target_label",
                "forecast_target_start",
                "forecast_target_end",
            )
        )
        if checks:
            checks = baseline["period_start"] == calendar_date(
                analysis["forecast_target_start"]
            ) and baseline["period_end"] == calendar_date(
                analysis["forecast_target_end"]
            )
        checks = checks and baseline["scope"] == entity.get("scope")
        for key in ("currency", "unit_multiplier"):
            checks = checks and v.get(key) is not None and v[key] == baseline[key]
        if not checks:
            baseline, status = (
                None,
                "forecast_scope_units_target_or_alignment_incompatible",
            )
    if baseline:
        result.financial_periods.append(baseline)
        v.update(
            baseline_revenue=baseline["amount"],
            forecast_vintage=baseline["available_at"],
        )
        prior, _ = financial.select(
            inputs,
            snapshot,
            analysis["analysis_id"],
            entity,
            "prior_actual",
            "revenue",
            cutoff,
        )
        if (
            prior
            and all(
                prior[k] == baseline[k]
                for k in ("scope", "currency", "unit_multiplier", "period_type")
            )
            and 350 <= (baseline["period_end"] - prior["period_end"]).days <= 380
            and abs(
                (baseline["period_end"] - baseline["period_start"]).days
                - (prior["period_end"] - prior["period_start"]).days
            )
            <= 10
        ):
            result.financial_periods.append(prior)
            v["prior_year_actual"] = prior["amount"]
            v["baseline_forecast_yoy"] = baseline["amount"] / prior["amount"] - 1
        rate = v.get("uplift_fraction")
        if rate is not None:
            v.update(
                adjustment=baseline["amount"] * rate,
                adjusted_forecast=baseline["amount"] * (1 + rate),
                forecast_status="available",
            )
            if v.get("prior_year_actual"):
                v["adjusted_forecast_yoy"] = (
                    v["adjusted_forecast"] / v["prior_year_actual"] - 1
                )
            return
        status = "missing_reviewed_display_fmi"
    v["forecast_status"] = "unavailable"
    v["forecast_missing_reason"] = status


def build_raw(
    inputs: Inputs, snapshot: Snapshot, policy: Policy, run_id: str
) -> tuple[list[FMIResult], dict[str, Row]]:
    from .inputs import validate_inputs

    validate_inputs(inputs)
    entities = {r["entity_id"]: r for r in inputs.entities}
    results, selections = [], {}
    for entity in inputs.entities:
        if not truth(entity.get("prospect")):
            continue
        analyses = [
            a
            for a in inputs.analyses
            if a["entity_id"] == entity["entity_id"]
            and truth(a.get("headline"))
            and truth(a.get("selected"))
        ]
        if len(analyses) == 1:
            analysis = analyses[0]
            result = raw_result(
                inputs, snapshot, analysis, entity, entities, policy, run_id
            )
            selections[entity["entity_id"]] = analysis
        else:
            result = FMIResult(
                entity["entity_id"],
                None,
                {
                    "name": entity["name"],
                    "fmi_status": "unavailable",
                    "forecast_status": "unavailable",
                    "run_id": run_id,
                    "policy_id": policy.version,
                },
                ["analysis:one_selected_headline_required"],
            )
        results.append(result)
    return results, selections


def calculate(
    inputs: Inputs, snapshot: Snapshot, policy: Policy, run_id: str
) -> tuple[list[FMIResult], Row]:
    results, selections = build_raw(inputs, snapshot, policy, run_id)
    entities = {e["entity_id"]: e for e in inputs.entities}
    cohort = rescale(results, policy)
    for result in results:
        if result.brand_id in selections:
            forecast(
                result,
                inputs,
                snapshot,
                selections[result.brand_id],
                entities[result.brand_id],
            )
        v = result.values
        v["narrative"] = (
            f"Raw FMI {v['raw_fmi']:.1f} ({v['raw_classification']}); "
            f"display {v['display_fmi']:.1f}; "
            f"scenario uplift {100 * v['uplift_fraction']:.2f}%."
            if v.get("display_fmi") is not None
            else "FMI unavailable: " + "; ".join(dict.fromkeys(result.gaps))
        )
    return results, cohort
