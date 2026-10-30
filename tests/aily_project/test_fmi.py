"""Isolated controlled-policy regressions; no database or cloud credentials."""

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from click.testing import CliRunner

from aily_project.cli import cli
from aily_project.services.fmi import financial, social
from aily_project.services.fmi.contract import FIELDS, canonical_record
from aily_project.services.fmi.extraction import candidate_mappings, extract
from aily_project.services.fmi.inputs import merge_reviews, seed_inputs, validate_inputs
from aily_project.services.fmi.models import FMIResult, Inputs, Snapshot, show_cutoff
from aily_project.services.fmi.policy import Policy
from aily_project.services.fmi.scoring import (
    calculate,
    classify,
    half_up,
    rescale,
    trend,
    uplift,
)
from aily_project.services.fmi.workbooks import delivery_payload

pytestmark = pytest.mark.unit


@pytest.fixture
def case():
    entities = [
        {
            "entity_id": eid,
            "name": eid,
            "prospect": eid == "brand",
            "light_code": eid.upper(),
            "ticker": None,
            "shared_symbol": eid + "-private",
            "financial_subject": eid,
            "scope": "standalone",
            "mapping_approved": True,
            "handle": eid,
            "profile_id": "p",
            "evidence": "identity approval",
        }
        for eid in ("brand", "peer")
    ]
    analysis = {
        "analysis_id": "a",
        "entity_id": "brand",
        "route": "show",
        "show_date": "2025-09-01",
        "timezone": "Europe/Paris",
        "headline": True,
        "selected": True,
        "reviewed": True,
        "financial_comparable": True,
        "social_coverage_reviewed": True,
        "forecast_alignment_reviewed": True,
        "forecast_target_label": "Q4",
        "forecast_target_start": "2025-11-01",
        "forecast_target_end": "2026-01-31",
        "evidence": "analysis approval",
    }
    inputs = Inputs(
        entities,
        [
            {
                "analysis_id": "a",
                "peer_entity_id": "peer",
                "approved": True,
                "comparable": True,
                "evidence": "calendar review",
            }
        ],
        [analysis],
    )
    snapshot = Snapshot(
        metadata={"authenticated": True, "extracted_at": "2026-10-30T10:00:00Z"}
    )
    for eid, amounts in (("brand", [100, 110, 133.1]), ("peer", [100, 105, 115.5])):
        for year, role, amount in zip(
            (2022, 2023, 2024), ("oldest", "earlier", "latest"), amounts, strict=True
        ):
            ident = f"{eid}-{year}"
            snapshot.financials.append(
                {
                    "source_row_id": ident,
                    "source_relation": "normalized.finance_fmp_financial_statements",
                    "symbol": eid + "-private",
                    "metric": "revenue",
                    "amount": amount,
                    "scope": "standalone",
                    "currency": "EUR",
                    "unit_multiplier": 1000000,
                    "period_label": str(year),
                    "period_start": f"{year}-01-01",
                    "period_end": f"{year}-12-31",
                    "period_type": "annual",
                    "kind": "actual",
                    "available_at": "2025-02-01T00:00:00Z",
                    "vintage_verified": True,
                    "source_classification": "reported",
                }
            )
            inputs.financial_review.append(
                {
                    "analysis_id": "a",
                    "entity_id": eid,
                    "role": role,
                    "metric": "revenue",
                    "source_row_id": ident,
                    "approved": True,
                    "evidence": "financial approval",
                }
            )
    for kind, role, year, amount in (
        ("forecast", "baseline", 2025, 200),
        ("actual", "prior_actual", 2024, 160),
    ):
        ident = role
        snapshot.financials.append(
            {
                "source_row_id": ident,
                "source_relation": "ai.light_financial_statements_forecast"
                if kind == "forecast"
                else "light.light_financial_statements_actuals",
                "company_code": "BRAND",
                "metric": "revenue",
                "amount": amount,
                "scope": "standalone",
                "currency": "EUR",
                "unit_multiplier": 1000000,
                "period_label": "Q4",
                "period_start": f"{year}-11-01",
                "period_end": f"{year + 1}-01-31",
                "period_type": "quarter",
                "kind": kind,
                "available_at": "2025-09-01T00:00:00Z",
                "vintage_verified": True,
            }
        )
        inputs.financial_review.append(
            {
                "analysis_id": "a",
                "entity_id": "brand",
                "role": role,
                "metric": "revenue",
                "source_row_id": ident,
                "approved": True,
                "evidence": "dated export approval",
            }
        )
    for i in range(10):
        day = "2025-09-02" if i < 5 else "2025-08-20"
        snapshot.posts.append(
            {
                "post_id": str(i),
                "profile_id": "p",
                "profile_username": "brand",
                "date_posted": day + "T12:00:00Z",
                "crawled_at": "2025-09-20T12:00:00Z",
                "like_count": 150 if i < 5 else 100,
                "comment_count": None,
                "video_view_count": 0 if i < 5 else None,
                "is_paid_partnership": None,
            }
        )
        inputs.post_review.append(
            {
                "analysis_id": "a",
                "post_key": f"p:{i}",
                "reviewed": True,
                "relevant": True,
                "evidence": "caption review",
            }
        )
    return inputs, snapshot


def test_end_to_end(case):
    inputs, snapshot = case
    results, cohort = calculate(inputs, snapshot, Policy(), "run")
    v = results[0].values
    assert v["earlier_growth"] == pytest.approx(0.1)
    assert v["latest_growth"] == pytest.approx(0.21)
    assert v["latest_gap_pp"] == pytest.approx(11)
    assert v["trend_score"] == 70
    assert v["raw_fmi"] == 94
    assert v["display_fmi"] == 84
    assert v["adjusted_forecast"] == pytest.approx(200 * (1 + uplift(84, Policy())))
    assert v["baseline_forecast_yoy"] == 0.25
    assert cohort["members"] == ["a"]
    payload = delivery_payload(results, snapshot, Policy(), cohort)
    assert len(payload["sheets"][0]["rows"]) == 1
    assert len(payload["sheets"][3]["rows"]) == 10
    assert results[0].peers[0]["pair_raw_fmi"] == 94
    assert set(payload["sheets"][0]["rows"][0]) == {f.key for f in FIELDS}


@pytest.mark.parametrize(
    "earlier,latest,score",
    [
        (0, 2.01, 70),
        (10, 7.99, 30),
        (5, 7, 80),
        (0, 2, 50),
        (10, 8, 80),
        (5, 10, 70),
        (4.9, 4.9, 50),
    ],
)
def test_trend_order(earlier, latest, score):
    assert trend(earlier, latest, Policy())[0] == score


@pytest.mark.parametrize(
    "raw,label",
    [
        (70, "High"),
        (69.999, "Medium"),
        (60, "Medium"),
        (40, "Neutral"),
        (39.999, "Low"),
    ],
)
def test_classification(raw, label):
    assert classify(raw) == label


@pytest.mark.parametrize(
    "display,rate",
    [
        (70, 0.009945409079974644),
        (80, 0.022179156792193538),
        (90, 0.04940585904245439),
        (98, 0.09373036022752759),
        (100, 0.11),
    ],
)
def test_uplift_benchmarks(display, rate):
    assert uplift(display, Policy()) == pytest.approx(rate, rel=1e-5)
    assert uplift(display - 0.1, Policy()) < uplift(display, Policy())


def test_rescale_and_membership():
    def result(name, raw, selected=True):
        return FMIResult(
            name,
            name,
            {"raw_fmi": raw, "fmi_status": "available", "headline_selection": selected},
        )

    r = [result("a", 40), result("b", 60), result("diagnostic", 100, False)]
    cohort = rescale(r, Policy())
    assert [x.values["display_fmi"] for x in r] == [70, 98, None]
    old = cohort["cohort_id"]
    r.append(result("c", 100))
    assert rescale(r, Policy())["cohort_id"] != old
    assert r[1].values["display_fmi"] == 79.3
    equal = [result("a", 42), result("b", 42)]
    rescale(equal, Policy())
    assert [x.values["display_fmi"] for x in equal] == [84, 84]
    assert rescale([], Policy())["members"] == []
    assert half_up(70.05) == 70.1


@pytest.mark.parametrize("change", ["peer", "likes", "oldest", "analysis"])
def test_missing_required_propagates_without_imputation(case, change):
    inputs, snapshot = case
    if change == "peer":
        inputs.peers.clear()
    elif change == "likes":
        snapshot.posts[0]["like_count"] = None
    elif change == "oldest":
        snapshot.financials.pop(0)
    else:
        inputs.analyses[0]["reviewed"] = False
    v = calculate(inputs, snapshot, Policy(), "run")[0][0].values
    assert v["fmi_status"] == "unavailable"
    assert v["display_fmi"] is None
    if change == "oldest":
        assert v["ir_status"] == "available"
        assert v["social_status"] == "available"


@pytest.mark.parametrize(
    "column,value",
    [
        ("available_at", None),
        ("available_at", "2026-01-01T00:00:00Z"),
        ("vintage_verified", False),
        ("amount", 0),
        ("scope", "group"),
        ("currency", "USD"),
        ("period_type", "YTD"),
    ],
)
def test_financial_and_forecast_gates(case, column, value):
    inputs, snapshot = case
    snapshot.financials[-2][column] = value
    v = calculate(inputs, snapshot, Policy(), "run")[0][0].values
    assert v["fmi_status"] == "available"
    assert v["uplift_fraction"] is not None
    assert v.get("adjusted_forecast") is None


def test_no_future_commercial_information(case):
    inputs, snapshot = case
    snapshot.financials[2].update(period_start="2025-01-01", period_end="2025-12-31")
    assert (
        calculate(inputs, snapshot, Policy(), "run")[0][0].values["fmi_status"]
        == "unavailable"
    )


def test_capture_filter_before_dedup_and_missing_zero(case):
    inputs, snapshot = case
    late = {
        **snapshot.posts[0],
        "crawled_at": "2026-01-01T00:00:00Z",
        "like_count": 9999,
    }
    unknown = {**snapshot.posts[1], "crawled_at": None, "like_count": 9999}
    snapshot.posts.extend([late, unknown])
    result = calculate(inputs, snapshot, Policy(), "run")[0][0]
    assert result.values["current_median_likes"] == 150
    assert len(result.social_posts) == 10
    assert result.values["current_median_views"] == 0
    assert result.values["views_lift"] is None
    assert result.values["current_median_comments"] is None
    assert result.values["current_usable_comments"] == 0


def test_context_does_not_change_fmi(case):
    inputs, snapshot = case
    before = calculate(inputs, snapshot, Policy(), "run")[0][0].values["raw_fmi"]
    for r in snapshot.posts:
        r.update(
            comment_count=999,
            video_view_count=333,
            post_type="video",
            is_paid_partnership=True,
        )
    after = calculate(inputs, snapshot, Policy(), "run")[0][0].values
    assert after["raw_fmi"] == before
    assert after["current_usable_comments"] == 5
    assert after["current_paid_true_posts"] == 5


def test_timezone_end_of_show_cutoff():
    cutoff = show_cutoff("2025-09-25", "Europe/Rome")
    assert cutoff.isoformat() == "2025-11-01T23:59:59.999999+01:00"
    assert cutoff.astimezone(UTC).hour == 22


def test_unreviewed_social_metrics_never_leak(case):
    inputs, snapshot = case
    inputs.post_review[0]["reviewed"] = False
    result = calculate(inputs, snapshot, Policy(), "run")[0][0]
    assert result.social_posts[0]["like_count"] is None
    assert result.values["current_usable_posts"] == 4


def test_conflicting_sources_and_unapproved_aggregation(case):
    inputs, snapshot = case
    snapshot.financials.append(deepcopy(snapshot.financials[0]))
    assert (
        calculate(inputs, snapshot, Policy(), "run")[0][0].values["fmi_status"]
        == "unavailable"
    )
    snapshot.financials.pop()
    inputs.financial_review[0]["aggregation_definition"] = "sum_quarters"
    assert (
        calculate(inputs, snapshot, Policy(), "run")[0][0].values["fmi_status"]
        == "unavailable"
    )


def test_parent_scope_is_not_automatically_substituted(case):
    inputs, snapshot = case
    inputs.entities[0].update(scope="group", proxy=True, proxy_label=None)
    assert not financial.identity_ready(inputs.entities[0])
    assert (
        calculate(inputs, snapshot, Policy(), "run")[0][0].values["fmi_status"]
        == "unavailable"
    )


def test_identity_candidates_and_aliases():
    inputs = Inputs(
        entities=[
            {
                "entity_id": "e",
                "name": "Brand",
                "aliases": "Legal company",
                "mapping_approved": False,
            }
        ]
    )
    registry = [
        {
            "company_code": "CODE",
            "company_name": "Legal company",
            "company_ticker": "SYMBOL",
        }
    ]
    assert not candidate_mappings(inputs, registry)
    inputs.entities[0]["mapping_approved"] = True
    rows = candidate_mappings(inputs, registry)
    assert rows[0]["company_code"] != rows[0]["company_ticker"]
    assert rows[0]["mapping_status"] == "candidate_requires_review"


def test_seed_92_and_preserve_reviews():
    root = Path(__file__).resolve().parents[2]
    inputs = seed_inputs(
        root
        / "scripts/fashion-momentum-index/handover/brand_peers_dinner prospects.xlsx"
    )
    assert sum(r.get("prospect") is True for r in inputs.entities) == 92
    assert len(inputs.analyses) == 92
    handles = {e["entity_id"]: e.get("handle") for e in inputs.entities}
    assert handles["chanel"] == "chanelofficial"
    assert handles["valentino"] == "maisonvalentino"
    existing = deepcopy(inputs)
    existing.entities[0]["handle"] = "custom"
    existing.entities[0]["mapping_approved"] = True
    assert merge_reviews(inputs, existing).entities[0]["handle"] == "custom"


def test_input_duplicate_and_contract_keys(case):
    inputs, _ = case
    inputs.analyses.append(deepcopy(inputs.analyses[0]))
    with pytest.raises(ValueError, match="duplicate"):
        validate_inputs(inputs)
    with pytest.raises(ValueError, match="contract"):
        canonical_record({"unknown_measurement": 1})
    assert len({f.key for f in FIELDS}) == len(FIELDS)
    assert next(f for f in FIELDS if f.key == "latest_growth").unit == "fraction"
    assert next(f for f in FIELDS if f.key == "latest_gap_pp").unit == "pp"


def test_read_only_check_precedes_schema_discovery():
    class DB:
        def __init__(self):
            self.calls = []

        def fetch_data_as_df(self, query, *, bind_params=()):
            self.calls.append(query)
            return pd.DataFrame(
                [
                    {
                        "transaction_read_only": "off",
                        "default_transaction_read_only": "on",
                    }
                ]
            )

    light, shared = DB(), DB()
    with pytest.raises(ValueError, match="read-only"):
        extract(light, shared, Inputs(), 2023, 2025)
    assert len(light.calls) == 1
    assert not shared.calls


def test_cli_help_does_not_initialize_settings():
    with patch("aily_project.services.fmi.runner.AilySettings") as settings:
        result = CliRunner().invoke(cli, ["fmi", "--help"])
    assert result.exit_code == 0
    assert "deliver" in result.output
    settings.assert_not_called()


def test_annual_windows_require_explicit_comparability(case):
    inputs, snapshot = case
    inputs.analyses[0].update(
        route="annual",
        cutoff="2025-12-31T23:59:59Z",
        current_start="2025-01-01",
        current_end="2025-12-31",
        baseline_start="2024-01-01",
        baseline_end="2024-03-31",
    )
    values, _, reasons = social.calculate(
        inputs,
        snapshot,
        inputs.analyses[0],
        inputs.entities[0],
        datetime(2025, 12, 31, tzinfo=UTC),
        Policy(),
    )
    assert values["social_status"] == "unavailable"
    assert "social:noncomparable_annual_windows" in reasons


def test_shared_only_peer_and_post_cutoff_correction(case):
    inputs, snapshot = case
    inputs.entities[1]["light_code"] = None
    assert calculate(inputs, snapshot, Policy(), "run")[0][0].values["raw_fmi"] == 94
    snapshot.financials[2].update(
        source_classification="corrected",
        correction_events=[{"changed_at": "2026-01-01T00:00:00Z"}],
    )
    assert (
        calculate(inputs, snapshot, Policy(), "run")[0][0].values["fmi_status"]
        == "unavailable"
    )


def test_followers_use_comparable_profile_and_true_timestamp_order(case):
    inputs, snapshot = case
    snapshot.profiles = [
        {
            "profile_id": "p",
            "profile_username": "brand",
            "crawled_at": "2025-09-20T00:30:00+02:00",
            "followers_count": 100,
        },
        {
            "profile_id": "p",
            "profile_username": "brand",
            "crawled_at": "2025-09-19T23:00:00Z",
            "followers_count": 120,
        },
        {
            "profile_id": "other",
            "profile_username": "brand",
            "crawled_at": "2025-09-21T00:00:00Z",
            "followers_count": 999,
        },
        {
            "profile_id": "p",
            "profile_username": "brand",
            "crawled_at": "2026-09-20T00:00:00Z",
            "followers_count": 999,
        },
    ]
    v = calculate(inputs, snapshot, Policy(), "run")[0][0].values
    assert v["follower_count"] == 120
    assert v["follower_growth"] == pytest.approx(0.2)
    snapshot.profiles.append({**snapshot.profiles[1], "followers_count": 121})
    v = calculate(inputs, snapshot, Policy(), "run")[0][0].values
    assert v.get("follower_count") is None


def test_social_timezone_day_boundaries(case):
    inputs, snapshot = case
    # Aug31 22:30 UTC is local Sept1 and therefore a current collection post.
    snapshot.posts[0]["date_posted"] = "2025-08-31T22:30:00Z"
    result = calculate(inputs, snapshot, Policy(), "run")[0][0]
    assert result.values["current_usable_posts"] == 5
    snapshot.posts[0]["date_posted"] = "2025-08-31T21:30:00Z"
    assert (
        calculate(inputs, snapshot, Policy(), "run")[0][0].values["social_status"]
        == "unavailable"
    )


def test_annual_positive_and_common_month_screen(case):
    inputs, snapshot = case
    a = inputs.analyses[0]
    a.update(
        route="annual",
        cutoff="2025-12-31T23:59:59Z",
        current_start="2025-01-01",
        current_end="2025-12-31",
        baseline_start="2024-01-01",
        baseline_end="2024-12-31",
    )
    snapshot.posts.clear()
    inputs.post_review.clear()
    for year in (2024, 2025):
        for i in range(21):
            post = f"{year}-{i}"
            snapshot.posts.append(
                {
                    "post_id": post,
                    "profile_id": "p",
                    "profile_username": "brand",
                    "date_posted": f"{year}-{1 + i % 3:02}-15T12:00:00Z",
                    "crawled_at": f"{year}-12-31T20:00:00Z",
                    "like_count": 100,
                }
            )
            inputs.post_review.append(
                {
                    "analysis_id": "a",
                    "post_key": "p:" + post,
                    "reviewed": True,
                    "evidence": "review",
                }
            )
    result = calculate(inputs, snapshot, Policy(), "run")[0][0]
    assert result.values["common_months"] == 3
    assert result.values["social_score"] == 50
    assert result.values["current_usable_posts"] == 21
    for row in snapshot.posts:
        row["date_posted"] = row["date_posted"][:5] + "01" + row["date_posted"][7:]
    assert (
        calculate(inputs, snapshot, Policy(), "run")[0][0].values["social_status"]
        == "unavailable"
    )


def test_positive_optional_financial_context(case):
    inputs, snapshot = case
    row = {
        **snapshot.financials[2],
        "source_row_id": "gross-profit",
        "metric": "gross_profit",
        "amount": 60,
    }
    snapshot.financials.append(row)
    inputs.financial_review.append(
        {
            "analysis_id": "a",
            "entity_id": "brand",
            "role": "latest",
            "metric": "gross_profit",
            "source_row_id": "gross-profit",
            "approved": True,
            "evidence": "review",
        }
    )
    result = calculate(inputs, snapshot, Policy(), "run")[0][0]
    assert result.values["latest_gross_profit"] == 60
    assert result.values["latest_gross_profit_margin"] == pytest.approx(60 / 133.1)
    assert result.values["raw_fmi"] == 94
    row["currency"] = "USD"
    assert (
        calculate(inputs, snapshot, Policy(), "run")[0][0].values.get(
            "latest_gross_profit"
        )
        is None
    )


def test_post_review_refresh_preserves_decisions(case):
    from aily_project.services.fmi.inputs import propose_mappings, propose_post_reviews

    inputs, snapshot = case
    first = deepcopy(inputs.post_review[0])
    inputs.post_review = [first]
    propose_post_reviews(inputs, snapshot)
    assert len(inputs.post_review) == 10
    assert inputs.post_review[0] == first
    assert inputs.post_review[1]["reviewed"] is False
    propose_post_reviews(inputs, snapshot)
    assert len(inputs.post_review) == 10
    inputs.entities[0]["mapping_approved"] = False
    inputs.entities[0]["profile_id"] = None
    propose_mappings(inputs, snapshot)
    assert inputs.entities[0]["profile_id"] == "p"


def test_schema_discovery_bounded_history_fallback_and_provenance():
    from aily_project.services.fmi.extraction import SPECS

    class DB:
        def __init__(self, tenant):
            self.tenant = tenant
            self.calls = []

        def fetch_data_as_df(self, query, *, bind_params=()):
            self.calls.append((query, bind_params))
            if "current_setting" in query:
                return pd.DataFrame(
                    [
                        {
                            "transaction_read_only": "on",
                            "default_transaction_read_only": "on",
                        }
                    ]
                )
            if "information_schema" in query:
                return pd.DataFrame(
                    [
                        {
                            "table_schema": rel.split(".")[0],
                            "table_name": rel.split(".")[1],
                            "column_name": c,
                        }
                        for rel, cols in SPECS.items()
                        if rel != "normalized.v_social_media_instagram_posts"
                        and rel.startswith(("light.", "ai.")) == self.tenant
                        for c in cols
                    ]
                )
            relation = query.split(" FROM ")[1].split()[0]
            if relation == "light.light_companies":
                return pd.DataFrame(
                    [
                        {
                            "company_code": "CODE",
                            "company_name": "Brand",
                            "company_ticker": "SYMBOL",
                        }
                    ]
                )
            if relation == "denormalized.finance_financial_statement_overrides":
                return pd.DataFrame(
                    [
                        {
                            "event_id": "1",
                            "symbol": "SYMBOL",
                            "calendar_year": 2024,
                            "period": "FY",
                            "metric": "revenue",
                            "action": "set",
                            "value": 120,
                            "reported_currency": "EUR",
                            "changed_at": "2026-01-01T00:00:00Z",
                        }
                    ]
                )
            if "financial_statements" in relation and relation.startswith(
                "normalized."
            ):
                return pd.DataFrame(
                    [
                        {
                            "symbol": "SYMBOL",
                            "calendar_year": 2024,
                            "period": "FY",
                            "revenue": 120,
                            "reported_currency": "EUR",
                            "crawled_at": "2025-01-01T00:00:00Z",
                        }
                    ]
                )
            return pd.DataFrame()

    light, shared = DB(True), DB(False)
    inputs = Inputs(
        entities=[{"entity_id": "brand", "name": "Brand", "handle": "brand"}]
    )
    snapshot = extract(light, shared, inputs, 2023, 2025, 100)
    view = next(
        r
        for r in snapshot.financials
        if r["source_relation"] == "normalized.v_finance_financial_statements"
    )
    assert len(view["source_candidates"]) == 3
    assert view["source_classification"] == "corrected_requires_vintage_review"
    assert view["available_at"] == "2026-01-01T00:00:00+00:00"
    assert not view["vintage_verified"]
    assert any("normalized.social_media_instagram_posts" in q for q, _ in shared.calls)
    for query, params in light.calls + shared.calls:
        assert query.startswith("SELECT ")
        assert "SELECT *" not in query
        assert "changed_by" not in query
        if "current_setting" not in query:
            assert "LIMIT %s" in query and params


def test_reviewed_symbol_alias_continuity_and_duplicate_peers(case):
    inputs, snapshot = case
    inputs.entities[1].update(shared_symbol="peer-new", aliases="peer-private")
    assert calculate(inputs, snapshot, Policy(), "run")[0][0].values["raw_fmi"] == 94
    duplicate = {**inputs.entities[1], "entity_id": "duplicate"}
    inputs.entities.append(duplicate)
    inputs.peers.append({**inputs.peers[0], "peer_entity_id": "duplicate"})
    inputs.financial_review.extend(
        [
            {**r, "entity_id": "duplicate"}
            for r in inputs.financial_review
            if r["entity_id"] == "peer"
        ]
    )
    result = calculate(inputs, snapshot, Policy(), "run")[0][0]
    assert result.values["fmi_status"] == "unavailable"
    assert any("duplicate_or_self_financial_subject" in r for r in result.gaps)


def test_policy_yaml_defaults_match():
    import yaml

    from aily_project.services.fmi import policy

    source = Path(policy.__file__).with_name("policy-reference.yaml")
    assert yaml.safe_load(source.read_text()) == Policy().model_dump()


def test_app_types_fail_closed():
    with pytest.raises(ValueError, match="boolean"):
        canonical_record({"proxy": "false"})
    with pytest.raises(ValueError, match="number"):
        canonical_record({"raw_fmi": float("nan")})
    with pytest.raises(ValueError, match="timestamp"):
        canonical_record({"forecast_vintage": "2025-01-01"})


def test_aggregation_and_fiscal_alignment(case):
    inputs, snapshot = case
    # Native labels differ; reviewed boundaries, not labels, establish alignment.
    snapshot.financials[0]["period_label"] = "Light FY2023"
    assert calculate(inputs, snapshot, Policy(), "run")[0][0].values["raw_fmi"] == 94
    snapshot.financials[1]["period_start"] = "2023-04-01"
    assert (
        calculate(inputs, snapshot, Policy(), "run")[0][0].values["fmi_status"]
        == "unavailable"
    )


def test_excel_cached_values_and_refresh_match_service(case, tmp_path, monkeypatch):
    import os

    from openpyxl import load_workbook

    from aily_project.services.fmi.workbooks import write_workbook

    if not os.environ.get("FMI_NODE_MODULES"):
        pytest.skip("Managed artifact runtime must be explicitly configured")
    inputs, snapshot = case
    result, cohort = calculate(inputs, snapshot, Policy(), "run")
    path = tmp_path / "test-delivery.xlsx"
    payload = delivery_payload(result, snapshot, Policy(), cohort)
    write_workbook(payload, path)
    book = load_workbook(path, data_only=True)
    assert book["Delivery"]["A2"].value == "Fashion Momentum Index delivery"
    assert book["Delivery"]["A3"].value == (
        "1 prospect. 1 reviewed FMI score. 1 adjusted forecast."
    )
    values = list(book["Delivery"].values)
    headers = list(values[3])
    for key in (
        "raw_fmi",
        "display_fmi",
        "uplift_fraction",
        "adjustment",
        "adjusted_forecast",
        "baseline_forecast_yoy",
        "adjusted_forecast_yoy",
    ):
        label = next(f.label for f in FIELDS if f.key == key)
        assert values[4][headers.index(label)] == pytest.approx(
            result[0].values[key], rel=1e-10
        )
    for sheet in book:
        assert all(c.data_type != "e" for row in sheet for c in row)
    assert book["Delivery"].freeze_panes == "D5"
    assert isinstance(values[4][headers.index("Cutoff")], datetime)
    book.close()
    original_approval = inputs.entities[0]["mapping_approved"]
    inputs.entities[0]["mapping_approved"] = False
    unavailable, cohort = calculate(inputs, snapshot, Policy(), "coverage-run")
    write_workbook(delivery_payload(unavailable, snapshot, Policy(), cohort), path)
    book = load_workbook(path, data_only=True)
    assert book["Delivery"]["A2"].value == "FMI coverage report"
    assert book["Delivery"]["A3"].value == (
        "1 prospect. 0 reviewed FMI scores. 0 adjusted forecasts. "
        "Inputs and historical vintages require review."
    )
    book.close()
    inputs.entities[0]["mapping_approved"] = original_approval
    old = result[0].values["raw_fmi"]
    for row in snapshot.posts[:5]:
        row["like_count"] = 120
    refreshed, cohort = calculate(inputs, snapshot, Policy(), "new-run")
    assert refreshed[0].values["raw_fmi"] != old
    write_workbook(delivery_payload(refreshed, snapshot, Policy(), cohort), path)
    book = load_workbook(path, data_only=True)
    assert (
        book["Delivery"].cell(5, headers.index("Raw fmi") + 1).value
        == refreshed[0].values["raw_fmi"]
    )
    book.close()
