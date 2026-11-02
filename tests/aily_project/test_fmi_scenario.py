"""Presentation simulation uses real source semantics without fabricated reviews."""

from copy import deepcopy
from datetime import date

import pytest

from aily_project.services.fmi.compact_inputs import materialize
from aily_project.services.fmi.flat_delivery import flat_payload
from aily_project.services.fmi.models import Snapshot
from aily_project.services.fmi.policy import Policy
from aily_project.services.fmi.scenario import (
    ACTUAL,
    CONSOLIDATED,
    FORECAST,
    financial_subject,
    forecast_scenario,
    select_period,
)
from aily_project.services.fmi.scoring import calculate

pytestmark = pytest.mark.unit


@pytest.fixture
def scenario_case():
    data = {
        "mode": "presentation",
        "forecast": {"label": "Q4 2026", "start": "2026-10-01", "end": "2026-12-31"},
        "brands": [
            {
                "id": "brand",
                "name": "Brand",
                "light_code": "CODE",
                "ticker": "TICK",
                "instagram": "brand",
                "profile_id": "p",
                "peers": ["peer", "missing"],
                "analysis": {
                    "route": "show",
                    "show_date": "2025-09-01",
                    "timezone": "Europe/Paris",
                },
            }
        ],
        "peer_entities": [
            {"id": "peer", "name": "Peer", "light_code": "PEER"},
            {"id": "missing", "name": "Missing", "shared_symbol": "MISSING"},
        ],
    }
    inputs = materialize(data)
    snapshot = Snapshot(
        registry=[
            {"company_code": "CODE", "company_ticker": "TICK"},
            {"company_code": "PEER", "company_ticker": None},
        ],
        metadata={"authenticated": True, "extracted_at": "2026-11-01T12:00:00Z"},
    )
    for code, values in (("CODE", [100, 110, 132]), ("PEER", [100, 105, 115.5])):
        for year, amount in zip((2023, 2024, 2025), values, strict=True):
            snapshot.financials.append(
                {
                    "company_code": code,
                    "year": year + 1,
                    "quarter": "Q3",
                    "reported_date": f"{year}-12-31",
                    "metric": "revenue",
                    "amount": amount,
                    "kind": "actual",
                    "source_relation": ACTUAL,
                    "source_row_id": f"{code}-{year}",
                    "source_classification": "current_snapshot",
                    "period_label": f"FY{year + 1} Q3",
                    "vintage_verified": False,
                }
            )
    snapshot.financials.append(
        {
            "company_code": "CODE",
            "year": 2027,
            "quarter": "Q3",
            "reported_date": "2026-12-31",
            "metric": "revenue",
            "amount": 200,
            "kind": "forecast",
            "source_relation": FORECAST,
            "source_row_id": "baseline",
            "period_label": "FY2027 Q3",
            "vintage_verified": False,
        }
    )
    for sample, day, likes in (
        ("current", "2025-09-02", 150),
        ("baseline", "2025-08-20", 100),
    ):
        for n in range(5):
            snapshot.posts.append(
                {
                    "post_id": f"{sample}-{n}",
                    "profile_id": "p",
                    "profile_username": "brand",
                    "date_posted": day + "T12:00:00Z",
                    "crawled_at": "2026-10-30T12:00:00Z",
                    "like_count": likes,
                }
            )
    return inputs, snapshot


def test_simulation_one_score_usable_peer_subset_and_both_uplifts(scenario_case):
    inputs, snapshot = scenario_case
    original = deepcopy(inputs)
    results, cohort = calculate(inputs, snapshot, Policy(), "r")
    v = results[0].values
    assert v["raw_fmi"] == pytest.approx(94)
    assert v["display_fmi"] == 84
    assert v["approved_peer_count"] == 0
    assert v["used_peer_count"] == 1
    assert "Missing" in v["peer_exclusion_reasons"]
    assert v["earlier_growth"] == pytest.approx(0.1)
    assert v["latest_growth"] == pytest.approx(0.2)
    assert v["baseline_revenue"] == 200
    assert v["adjusted_forecast"] == pytest.approx(200 * (1 + v["uplift_fraction"]))
    assert v["legacy_adjusted_forecast"] == pytest.approx(219.6)
    assert v["prior_year_actual"] == 132
    assert v["forecast_vintage"] is None
    assert v["currency"] is None and v["unit_multiplier"] is None
    assert v["historical_status"] == "current_source_simulation_not_replay"
    assert all(not p["vintage_verified"] for p in results[0].financial_periods)
    assert all(not p["reviewed"] for p in results[0].social_posts)
    assert cohort["members"] == ["brand-headline"]
    assert inputs == original
    row = flat_payload(results, inputs, snapshot, [])["sheets"][0]["rows"][0]
    assert row["calculation_mode"] == "presentation"
    assert row["release_status"] == "presentation_simulation_not_reviewed_replay"
    assert row["latest_period_end"] == "2025-12-31"
    assert row["baseline_period_end"] == "2026-12-31"
    assert row["observed_context_historical_eligible"] is False


def test_authorized_parent_fallback_uses_same_forecast_subject(scenario_case):
    inputs, snapshot = scenario_case
    entity = inputs.entities[0]
    entity.update(light_code=None, ticker=None, shared_symbol=None)
    entity["parent"] = {
        "name": "Parent",
        "light_code": "CODE",
        "ticker": "TICK",
        "authorized": True,
        "evidence": "Ownership source and user authorization",
    }
    original = deepcopy(inputs)
    result = calculate(inputs, snapshot, Policy(), "parent")[0][0]
    assert result.values["raw_fmi"] == pytest.approx(94)
    assert result.values["financial_subject"] == "Parent"
    assert result.values["baseline_revenue"] == 200
    assert result.values["scope"] == "parent_group"
    assert result.values["parent_fallback_status"] == "used_authorized_parent_proxy"
    assert "NOT standalone" in result.values["proxy_label"]
    assert not inputs.entities[0]["mapping_approved"]
    assert inputs == original
    row = flat_payload([result], inputs, snapshot, [])["sheets"][0]["rows"][0]
    assert row["actual_revenue_candidate_count"] == 3
    assert row["parent_name"] == "Parent"


def test_forecast_reuses_score_subject_not_snapshot_policy(scenario_case):
    inputs, snapshot = scenario_case
    entity = inputs.entities[0]
    entity["parent"] = {
        "name": "Other group",
        "light_code": "PEER",
        "authorized": True,
        "evidence": "ownership",
    }
    result = calculate(inputs, snapshot, Policy(), "subject")[0][0]
    assert result.values["light_code"] == "CODE"
    # A later policy/input state must not silently pair a parent's baseline with
    # the already-calculated brand score.
    entity["parent"]["prefer"] = True
    forecast_scenario(result, inputs, snapshot, inputs.analyses[0], entity)
    assert result.values["baseline_source_row_id"] == "baseline"
    assert result.values["baseline_revenue"] == 200


@pytest.mark.parametrize("authorized,evidence", [(False, "source"), (True, "")])
def test_parent_requires_authorization_and_evidence(
    scenario_case, authorized, evidence
):
    inputs, snapshot = scenario_case
    entity = inputs.entities[0]
    entity.update(light_code=None, ticker=None)
    entity["parent"] = {
        "name": "Parent",
        "light_code": "CODE",
        "authorized": authorized,
        "evidence": evidence,
    }
    result = calculate(inputs, snapshot, Policy(), "parent")[0][0]
    assert result.values.get("raw_fmi") is None


def test_parent_fallback_never_changes_strict_replay(scenario_case):
    inputs, snapshot = scenario_case
    entity = inputs.entities[0]
    entity.update(light_code=None, ticker=None)
    entity["parent"] = {
        "name": "Parent",
        "light_code": "CODE",
        "authorized": True,
        "evidence": "source",
    }
    analysis = {**inputs.analyses[0], "calculation_mode": "strict_replay"}
    assert financial_subject(entity, snapshot, analysis, Policy()) is entity


def test_complete_brand_series_precedes_parent_proxy(scenario_case):
    inputs, snapshot = scenario_case
    entity = inputs.entities[0]
    entity["parent"] = {
        "name": "Peer parent",
        "light_code": "PEER",
        "authorized": True,
        "evidence": "source",
    }
    result = calculate(inputs, snapshot, Policy(), "parent")[0][0]
    assert result.values["light_code"] == "CODE"
    assert result.values["parent_fallback_status"] == "brand_series_retained"


def test_explicit_private_parent_preference_is_honored(scenario_case):
    inputs, snapshot = scenario_case
    entity = inputs.entities[0]
    entity["parent"] = {
        "name": "Parent group",
        "light_code": "CODE",
        "ticker": "TICK",
        "authorized": True,
        "prefer": True,
        "evidence": "Ownership and authorized parent preference",
    }
    result = calculate(inputs, snapshot, Policy(), "private")[0][0]
    assert result.values["financial_subject"] == "Parent group"
    assert result.values["scope"] == "parent_group"
    assert result.values["baseline_revenue"] == 200
    assert result.values["raw_fmi"] == pytest.approx(94)


def test_parent_peer_cannot_compare_to_itself(scenario_case):
    inputs, snapshot = scenario_case
    peer = inputs.entities[1]
    peer["light_code"] = None
    peer["parent"] = {
        "name": "Parent",
        "light_code": "CODE",
        "authorized": True,
        "evidence": "source",
    }
    result = calculate(inputs, snapshot, Policy(), "parent")[0][0]
    assert result.values.get("raw_fmi") is None
    assert (
        "duplicate_or_self_financial_subject" in result.values["peer_exclusion_reasons"]
    )


def test_missing_row_currency_uses_exact_light_registry(scenario_case):
    inputs, snapshot = scenario_case
    snapshot.registry[0]["currency"] = "USD"
    result = calculate(inputs, snapshot, Policy(), "currency")[0][0]
    assert result.values["raw_fmi"] == pytest.approx(94)
    assert result.values["currency"] == "USD"
    assert (
        result.financial_periods[1]["currency_basis"]
        == "light_registry_denomination_assumption"
    )
    assert result.financial_periods[1]["unit_multiplier"] is None


def test_source_currency_precedes_registry_trading_denomination(scenario_case):
    inputs, snapshot = scenario_case
    snapshot.registry[0]["currency"] = "HKD"
    for row in snapshot.financials:
        if row.get("company_code") == "CODE":
            row["currency"] = "EUR"
    result = calculate(inputs, snapshot, Policy(), "currency")[0][0]
    assert result.values["raw_fmi"] == pytest.approx(94)
    assert result.values["currency"] == "EUR"


def test_forecast_missing_currency_uses_consistent_subject_history(scenario_case):
    inputs, snapshot = scenario_case
    snapshot.registry[0]["currency"] = "HKD"
    for row in snapshot.financials:
        if row.get("company_code") == "CODE" and row["kind"] == "actual":
            row["currency"] = "EUR"
    result = calculate(inputs, snapshot, Policy(), "forecast-currency")[0][0]
    assert result.values["baseline_currency"] == "EUR"
    assert (
        result.values["baseline_currency_basis"]
        == "same_subject_source_history_assumption"
    )
    assert result.values["forecast_status"] == "available"
    assert result.values["baseline_revenue"] == 200


def test_annual_common_months_filter_precedes_medians(scenario_case):
    inputs, snapshot = scenario_case
    analysis = inputs.analyses[0]
    analysis.update(
        route="annual",
        current_start="2025-01-01",
        current_end="2025-12-31",
        baseline_start="2024-01-01",
        baseline_end="2024-12-31",
        common_months_only=True,
    )
    snapshot.posts = []
    for year, month, likes in (
        (2024, 1, 10000),
        (2024, 2, 100),
        (2025, 2, 200),
        (2025, 3, 20000),
    ):
        for n in range(20):
            snapshot.posts.append(
                {
                    "profile_username": "brand",
                    "profile_id": "p",
                    "post_id": f"{year}-{month}-{n}",
                    "date_posted": f"{year}-{month:02d}-01T12:00:00Z",
                    "crawled_at": "2026-10-30T12:00:00Z",
                    "like_count": likes,
                }
            )
    result = calculate(inputs, snapshot, Policy(annual_min_common_months=1), "months")[
        0
    ][0]
    assert result.values["current_median_likes"] == 200
    assert result.values["baseline_median_likes"] == 100
    assert result.values["current_usable_posts"] == 20
    assert result.values["baseline_excluded_posts"] == 20
    assert result.values["common_months"] == 1
    assert (
        sum(
            p["inclusion_reason"] == "outside_common_months"
            for p in result.social_posts
        )
        == 40
    )


def test_strict_mode_does_not_release_current_simulation_rows(scenario_case):
    inputs, snapshot = scenario_case
    inputs.analyses[0]["calculation_mode"] = "strict_replay"
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    assert results[0].values.get("raw_fmi") is None
    assert results[0].values.get("adjusted_forecast") is None


@pytest.mark.parametrize("change", ["missing", "conflict", "annual", "proxy", "ticker"])
def test_invalid_financial_inputs_do_not_get_neutral_imputation(scenario_case, change):
    inputs, snapshot = scenario_case
    if change == "missing":
        snapshot.financials = [
            r for r in snapshot.financials if r["source_row_id"] != "CODE-2025"
        ]
    elif change == "conflict":
        snapshot.financials.append(
            {**snapshot.financials[2], "amount": 999, "source_row_id": "conflict"}
        )
    elif change == "annual":
        snapshot.financials[2]["quarter"] = "FY"
    elif change == "proxy":
        inputs.entities[0]["proxy"] = True
    else:
        inputs.entities[0]["ticker"] = "WRONG"
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    assert results[0].values.get("raw_fmi") is None
    assert results[0].values["social_score"] == 100
    assert results[0].gaps


def test_fiscal_end_date_tolerance_not_year_quarter_label(scenario_case):
    inputs, snapshot = scenario_case
    snapshot.financials[2]["reported_date"] = "2025-12-27"
    row, _ = select_period(
        inputs.entities[0], snapshot, date(2025, 12, 31), "latest", "a", 14
    )
    assert row and row["amount"] == 132
    assert row["period_alignment"] == "fiscal_end_date_native_quarter_proxy"
    assert row["period_boundaries_verified"] is False
    snapshot.financials[2]["reported_date"] = "2025-11-30"
    row, _ = select_period(
        inputs.entities[0], snapshot, date(2025, 12, 31), "latest", "a", 14
    )
    assert row is None


def test_missing_baseline_preserves_fmi_and_policy_rate(scenario_case):
    inputs, snapshot = scenario_case
    snapshot.financials = [r for r in snapshot.financials if r["kind"] != "forecast"]
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    assert results[0].values["raw_fmi"] == pytest.approx(94)
    assert results[0].values["uplift_fraction"] > 0
    assert results[0].values["forecast_status"] == "unavailable"


def test_simulation_review_exclusion_still_applies(scenario_case):
    inputs, snapshot = scenario_case
    inputs.post_review.append(
        {
            "analysis_id": "brand-headline",
            "post_key": "p:current-0",
            "reviewed": True,
            "relevant": False,
            "evidence": "review",
        }
    )
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    assert results[0].values["current_usable_posts"] == 4
    assert results[0].values.get("raw_fmi") is None


def test_simulation_filters_capture_before_deduplication(scenario_case):
    inputs, snapshot = scenario_case
    snapshot.posts.append(
        {**snapshot.posts[0], "like_count": 999, "crawled_at": "2026-11-02T12:00:00Z"}
    )
    snapshot.posts.append(
        {**snapshot.posts[0], "post_id": "unknown", "crawled_at": None}
    )
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    assert results[0].values["current_median_likes"] == 150
    assert results[0].values["current_usable_posts"] == 5


def test_no_dates_fallback_is_explicit_and_context_does_not_change_score(scenario_case):
    inputs, snapshot = scenario_case
    inputs.analyses[0].pop("route")
    snapshot.posts = []
    for year, likes in ((2024, 100), (2025, 150)):
        for month in (10, 11, 12):
            for n in range(7):
                snapshot.posts.append(
                    {
                        "post_id": f"{year}-{month}-{n}",
                        "profile_id": "p",
                        "profile_username": "brand",
                        "date_posted": f"{year}-{month:02d}-15T12:00:00Z",
                        "crawled_at": "2026-10-30T12:00:00Z",
                        "like_count": likes,
                    }
                )
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    assert results[0].values["route"] == "period"
    assert results[0].values["current_usable_posts"] == 21
    assert results[0].values["common_months"] == 3
    first = results[0].values["raw_fmi"]
    for post in snapshot.posts:
        post.update(comment_count=99999, video_view_count=1000000)
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    assert results[0].values["raw_fmi"] == first


def test_shared_only_private_peer_and_null_ticker(scenario_case):
    inputs, snapshot = scenario_case
    inputs.entities[1].pop("light_code")
    inputs.entities[1]["shared_symbol"] = "PRIVATE-PEER"
    for row in snapshot.financials:
        if row["company_code"] == "PEER":
            row.update(symbol="PRIVATE-PEER", source_relation=CONSOLIDATED)
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    assert results[0].values["used_peer_count"] == 1
    assert results[0].values["raw_fmi"] == pytest.approx(94)
    selected = [r for r in results[0].financial_periods if r["entity_id"] == "peer"]
    assert all(
        r["selection_basis"] == "configured_shared_symbol_not_registry_verified"
        for r in selected
    )


def test_duplicate_self_symbol_is_not_a_peer(scenario_case):
    inputs, snapshot = scenario_case
    inputs.entities[1].update(shared_symbol="TICK")
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    assert results[0].values["used_peer_count"] == 0
    assert "duplicate_or_self" in results[0].values["peer_exclusion_reasons"]
    assert results[0].values.get("raw_fmi") is None


def test_multiple_usable_peers_use_one_median_and_one_headline(scenario_case):
    inputs, snapshot = scenario_case
    for year, amount in ((2023, 100), (2024, 115), (2025, 149.5)):
        snapshot.financials.append(
            {
                "symbol": "MISSING",
                "period": "Q4",
                "date": f"{year}-12-31",
                "metric": "revenue",
                "kind": "actual",
                "amount": amount,
                "source_relation": CONSOLIDATED,
                "source_row_id": f"extra-{year}",
            }
        )
    results, cohort = calculate(inputs, snapshot, Policy(), "r")
    assert len(results) == len(cohort["members"]) == 1
    assert results[0].values["used_peer_count"] == 2
    assert results[0].values["earlier_peer_median_growth"] == pytest.approx(0.1)
    assert results[0].values["latest_peer_median_growth"] == pytest.approx(0.2)
    assert results[0].values["raw_fmi"] == pytest.approx(65)


def test_source_conflict_and_correction_provenance(scenario_case):
    inputs, snapshot = scenario_case
    correction = {"event_id": 42, "changed_at": None}
    shared = {
        **snapshot.financials[2],
        "company_code": None,
        "symbol": "TICK",
        "source_relation": CONSOLIDATED,
        "source_row_id": "shared",
        "correction_events": [correction],
        "source_classification": "corrected_current_snapshot",
    }
    inputs.entities[0]["shared_symbol"] = "TICK"
    snapshot.financials.append(shared)
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    latest = next(
        r
        for r in results[0].financial_periods
        if r["entity_id"] == "brand" and r["role"] == "latest"
    )
    assert latest["underlying_candidates"][0]["correction_events"] == [correction]
    assert latest["source_classification"] == "corrected_current_snapshot"
    shared["amount"] = 999
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    assert results[0].values.get("raw_fmi") is None
    assert any("light_shared_amount_conflict" in reason for reason in results[0].gaps)


def test_zero_likes_and_missing_likes_are_distinct(scenario_case):
    inputs, snapshot = scenario_case
    for post in snapshot.posts[:5]:
        post["like_count"] = 0
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    assert results[0].values["current_usable_posts"] == 5
    assert results[0].values["social_score"] == 0
    snapshot.posts[0]["like_count"] = None
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    assert results[0].values["current_usable_posts"] == 4
    assert results[0].values.get("raw_fmi") is None


def test_latest_actual_is_independent_of_forecast_yoy_period(scenario_case):
    inputs, snapshot = scenario_case
    inputs.analyses[0]["financial_basis"] = "latest_available"
    for year, amount in ((2024, 120), (2025, 144), (2026, 180)):
        snapshot.financials.append(
            {
                **snapshot.financials[0],
                "reported_date": f"{year}-06-30",
                "quarter": "Q1",
                "year": year + 1,
                "period_label": f"FY{year + 1} Q1",
                "amount": amount,
                "source_row_id": f"new-{year}",
            }
        )
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    v = results[0].values
    assert v["latest_period_end"] == date(2026, 6, 30)
    assert v["earlier_growth"] == pytest.approx(0.2)
    assert v["latest_growth"] == pytest.approx(0.25)
    assert v["prior_year_actual"] == 132  # Forecast December YoY, not June actual.
    assert v["baseline_period_label"] == "FY2027 Q3"
    assert v["peer_calendar_alignment_status"] == "different_native_end_dates"
    assert "FY2026 Q3" in v["used_peer_periods"]
    assert v["latest_actual_age_days"] == 124
    assert v["financial_freshness_status"] == "within_180_days"


def test_retail_year_end_and_53_week_yoy_keep_native_labels(scenario_case):
    inputs, snapshot = scenario_case
    inputs.analyses[0]["financial_basis"] = "latest_available"
    endings = {2023: "2024-02-03", 2024: "2025-02-01", 2025: "2026-01-31"}
    for row in snapshot.financials:
        row["quarter"] = "Q4"
        if row["kind"] == "actual":
            year = int(row["source_row_id"].rsplit("-", 1)[1])
            row.update(reported_date=endings[year], period_label=f"Retail FY{year} Q4")
        else:
            row.update(reported_date="2027-01-31", period_label="Retail FY2026 Q4")
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    v = results[0].values
    assert v["raw_fmi"] == pytest.approx(94)
    assert v["forecast_status"] == "available"
    assert v["forecast_target_label"] == "Q4 2026"
    assert v["baseline_period_label"] == "Retail FY2026 Q4"
    assert v["baseline_period_end"] == date(2027, 1, 31)
    assert v["baseline_period_start"] == date(2026, 11, 1)
    assert v["forecast_target_end_difference_days"] == 31
    assert v["prior_year_actual_period_end"] == date(2026, 1, 31)
    assert v["financial_freshness_status"] == "older_than_180_days"
    assert v["forecast_calendar_alignment_status"] != "matches_requested_end"


@pytest.mark.parametrize("change", ["future", "incomplete", "conflict"])
def test_latest_selector_does_not_silently_use_old_complete_series(
    scenario_case, change
):
    inputs, snapshot = scenario_case
    inputs.analyses[0]["financial_basis"] = "latest_available"
    snapshot.financials.append(
        {
            **snapshot.financials[2],
            "reported_date": "2026-12-31" if change == "future" else "2026-06-30",
            "quarter": "Q1",
            "amount": 999,
            "source_row_id": "new",
        }
    )
    if change == "conflict":
        snapshot.financials.append(
            {**snapshot.financials[-1], "amount": 888, "source_row_id": "conflict"}
        )
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    v = results[0].values
    if change == "future":
        assert v["raw_fmi"] == pytest.approx(94)
        assert v["latest_period_end"] == date(2025, 12, 31)
    else:
        assert v.get("raw_fmi") is None
        assert results[0].gaps


def test_latest_forecast_not_furthest_future_and_no_unrelated_horizon(scenario_case):
    inputs, snapshot = scenario_case
    inputs.analyses[0]["financial_basis"] = "latest_available"
    snapshot.financials.append(
        {
            **snapshot.financials[6],
            "reported_date": "2027-12-31",
            "source_row_id": "far-future",
            "amount": 999,
        }
    )
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    assert results[0].values["baseline_revenue"] == 200
    snapshot.financials = [
        r for r in snapshot.financials if r["source_row_id"] != "baseline"
    ]
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    assert results[0].values["forecast_status"] == "unavailable"
    assert results[0].values["raw_fmi"] == pytest.approx(94)


def test_latest_financial_basis_rejected_for_strict_replay():
    with pytest.raises(ValueError, match="only for presentation"):
        materialize({"financial_basis": "latest_available", "brands": []})
    with pytest.raises(ValueError, match="Financial basis must"):
        materialize({"financial_basis": "whatever", "brands": []})


def test_forecast_yoy_missing_does_not_erase_latest_fmi_or_adjustment(scenario_case):
    inputs, snapshot = scenario_case
    inputs.analyses[0]["financial_basis"] = "latest_available"
    # Same end dates cannot make actual Q3 comparable to forecast Q4.
    snapshot.financials[6]["quarter"] = "Q4"
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    v = results[0].values
    assert v["forecast_status"] == "available"
    assert v["adjusted_forecast"] > 200
    assert v.get("prior_year_actual") is None
    assert v.get("baseline_forecast_yoy") is None
    assert v.get("adjusted_forecast_yoy") is None
    assert "missing_native_quarter" in v["prior_year_actual_status"]


def test_forecast_tied_nearest_ends_are_not_chosen_arbitrarily(scenario_case):
    inputs, snapshot = scenario_case
    inputs.analyses[0]["financial_basis"] = "latest_available"
    snapshot.financials[6]["reported_date"] = "2026-12-30"
    snapshot.financials.append(
        {
            **snapshot.financials[6],
            "reported_date": "2027-01-01",
            "source_row_id": "equidistant",
        }
    )
    results, _ = calculate(inputs, snapshot, Policy(), "r")
    assert results[0].values["raw_fmi"] == pytest.approx(94)
    assert results[0].values["forecast_status"] == "unavailable"
    assert "conflicting_native_quarter" in results[0].values["forecast_missing_reason"]
