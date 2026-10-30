"""Pairwise configuration and scoring; synthetic inputs, no cloud access."""

import math
import runpy
from pathlib import Path

import pandas as pd
import pytest

FMI = runpy.run_path(str(Path(__file__).parents[1] / "fmi.py"))
pytestmark = pytest.mark.unit


def pair_inputs() -> tuple[
    pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame
]:
    financials, posts, labels, analysis = FMI["demo_inputs"]()
    third = financials.loc[financials["entity"].eq("example_peer_1")].copy()
    third["entity"] = "example_peer_3"
    third["amount"] = [100, 101, 101.5]
    financials = pd.concat([financials, third], ignore_index=True)
    pairs = pd.DataFrame(
        [
            {
                "brand": analysis["brand"],
                "financial_entity": analysis["financial_entity"],
                "peer_entity": f"example_peer_{i}",
            }
            for i in (1, 2, 3)
        ]
    )
    return financials, posts, labels, pd.DataFrame([analysis]), pairs


def test_three_peers_generate_three_distinct_scores() -> None:
    financials, posts, labels, settings, pairs = pair_inputs()
    analyses = FMI["comparison_analyses"](settings, pairs)
    scores = [
        FMI["score_analysis"](financials, posts, labels, analysis)
        for analysis in analyses
    ]
    assert len(scores) == 3
    assert [score["peer_entity"] for score in scores] == [
        "example_peer_1",
        "example_peer_2",
        "example_peer_3",
    ]
    assert len({round(score["fmi"], 4) for score in scores}) == 3
    assert scores[0]["fmi"] == pytest.approx(73)
    assert scores[1]["fmi"] == pytest.approx(68)
    assert {score["social_score"] for score in scores} == {80}
    assert all(score["comparison_mode"] == "single-peer" for score in scores)
    assert all(
        "peer_1" not in analysis and "peer_2" not in analysis for analysis in analyses
    )


def test_multiple_brands_use_only_their_configured_edges() -> None:
    _, _, _, settings, pairs = pair_inputs()
    second = settings.copy()
    second["brand"] = "Second Brand"
    second["financial_entity"] = "second_brand"
    settings = pd.concat([settings, second], ignore_index=True)
    pairs = pd.concat(
        [
            pairs,
            pd.DataFrame(
                [
                    {
                        "brand": "Second Brand",
                        "financial_entity": "second_brand",
                        "peer_entity": "example_peer_2",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    analyses = FMI["comparison_analyses"](settings, pairs)
    assert len(analyses) == 4
    assert sum(row["financial_entity"] == "second_brand" for row in analyses) == 1
    assert analyses[-1]["peer_entity"] == "example_peer_2"


def test_missing_peer_does_not_invalidate_other_pairs() -> None:
    financials, posts, labels, settings, pairs = pair_inputs()
    financials = financials.loc[financials["entity"].ne("example_peer_2")]
    scores = [
        FMI["score_analysis"](financials, posts, labels, analysis)
        for analysis in FMI["comparison_analyses"](settings, pairs)
    ]
    assert math.isfinite(scores[0]["fmi"])
    assert math.isnan(scores[1]["fmi"])
    assert "example_peer_2" in scores[1]["gaps"]
    assert math.isfinite(scores[2]["fmi"])


def test_two_brands_generate_only_assigned_pair_scores() -> None:
    financials, posts, labels, settings, pairs = pair_inputs()
    second_settings = settings.copy()
    second_settings["brand"] = "Second Brand"
    second_settings["financial_entity"] = "second_brand"
    second_settings["handle"] = "second_handle"
    second_financials = financials.loc[financials["entity"].eq("example_brand")].copy()
    second_financials["entity"] = "second_brand"
    second_posts = posts.copy()
    second_posts["handle"] = "second_handle"
    financials = pd.concat([financials, second_financials], ignore_index=True)
    posts = pd.concat([posts, second_posts], ignore_index=True)
    settings = pd.concat([settings, second_settings], ignore_index=True)
    pairs = pd.concat(
        [
            pairs,
            pd.DataFrame(
                [
                    {
                        "brand": "Second Brand",
                        "financial_entity": "second_brand",
                        "peer_entity": "example_peer_2",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    scores = [
        FMI["score_analysis"](financials, posts, labels, analysis)
        for analysis in FMI["comparison_analyses"](settings, pairs)
    ]
    assert len(scores) == 4
    assert all(math.isfinite(score["fmi"]) for score in scores)
    assert scores[-1]["brand"] == "Second Brand"
    assert scores[-1]["peer_entity"] == "example_peer_2"
    assert scores[-1]["fmi"] == pytest.approx(68)
    assert all(score["baseline"] == 100000000 for score in scores)


@pytest.mark.parametrize("bad_config", ["duplicate", "self", "blank", "unknown_brand"])
def test_invalid_peer_configuration_is_explicit(bad_config: str) -> None:
    _, _, _, settings, pairs = pair_inputs()
    if bad_config == "duplicate":
        pairs = pd.concat([pairs, pairs.iloc[[0]]], ignore_index=True)
    elif bad_config == "self":
        pairs.loc[0, "peer_entity"] = "example_brand"
    elif bad_config == "blank":
        pairs.loc[0, "peer_entity"] = " "
    else:
        pairs.loc[0, "financial_entity"] = "unknown"
    with pytest.raises(ValueError):
        FMI["comparison_analyses"](settings, pairs)


def test_entity_periods_and_forecast_roles_are_csv_driven() -> None:
    entities = pd.DataFrame(
        [
            {
                "entity": "brand",
                "oldest_year": 2024,
                "oldest_quarter": "Q2",
                "earlier_year": 2025,
                "earlier_quarter": "Q2",
                "latest_year": 2026,
                "latest_quarter": "Q2",
                "target_year": 2027,
                "target_quarter": "Q3",
                "last_year_target_year": 2026,
                "last_year_target_quarter": "Q3",
            }
        ]
    )
    actuals = FMI["entity_period_choices"](entities, ["brand"])
    assert actuals["year"].tolist() == [2024, 2025, 2026]
    assert actuals["classification"].eq("Actual").all()
    target = FMI["entity_period_choices"](
        entities, ["brand"], ("target", "last_year_target")
    )
    assert target["classification"].tolist() == ["Forecast", "Actual"]
    with pytest.raises(ValueError, match="Add missing"):
        FMI["entity_period_choices"](entities, ["missing"])


@pytest.mark.parametrize("score,uplift_pct", [(52, 0), (70.5, 5.1)])
def test_burberry_sales_scenario_targets_fy2026_q4_forecast(
    score: float, uplift_pct: float
) -> None:
    entities = pd.read_csv(Path(__file__).parents[1] / "inputs/entities.csv")
    choices = FMI["entity_period_choices"](
        entities, ["burberry"], ("target", "last_year_target")
    )
    indexed = choices.set_index("period_role")

    assert indexed.loc["target", ["year", "quarter", "classification"]].tolist() == [
        2026,
        "Q4",
        "Forecast",
    ]
    assert indexed.loc[
        "last_year_target", ["year", "quarter", "classification"]
    ].tolist() == [2025, "Q4", "Actual"]

    # Synthetic rows exercise the notebook's full selection-to-uplift path.
    # Neither the FY2026 Q4 Actual nor the old FY2027 Q3 Forecast is the baseline.
    raw = pd.DataFrame(
        [
            {
                "entity": "burberry",
                "year": year,
                "quarter": quarter,
                "classification": classification,
                "amount": amount,
                "metric": "revenue",
                "reported_date": date,
            }
            for year, quarter, classification, amount, date in [
                (2026, "Q4", "Forecast", 1000, "2026-03-31"),
                (2026, "Q4", "Actual", 9000, "2026-03-31"),
                (2025, "Q4", "Actual", 800, "2025-03-31"),
                (2027, "Q3", "Forecast", 5000, "2026-12-30"),
            ]
        ]
    )
    selected = FMI["preview_periods"](raw, choices, "2026-10-28T23:59:59Z")
    amounts = selected.set_index("period_role")["amount"]
    scenario = FMI["sales_scenario"](
        score, float(amounts["target"]), float(amounts["last_year_target"])
    )
    assert scenario["baseline"] == 1000
    assert scenario["uplift_pct"] == pytest.approx(uplift_pct)
    assert scenario["adjusted_forecast"] == pytest.approx(1000 * (1 + uplift_pct / 100))
    assert scenario["forecast_yoy_pct"] == pytest.approx(
        (scenario["adjusted_forecast"] / 800 - 1) * 100
    )


def test_preview_pair_uses_raw_ratios_without_review_attestation() -> None:
    financials, posts, labels, settings, pairs = pair_inputs()
    analysis = FMI["comparison_analyses"](settings, pairs)[0]
    analysis["comparability_reviewed"] = False
    analysis["coverage_reviewed"] = False
    raw = financials.copy()
    raw["reported_date"] = raw["period_end"]
    raw["metric"] = "revenue"
    raw["scope"] = None
    raw["currency"] = None
    raw["unit_multiplier"] = None
    preview = FMI["score_analysis"](raw, posts, labels, analysis, preview=True)
    assert preview["fmi"] == pytest.approx(73)
    assert preview["validated_collection_fmi"] is False
    assert "PROVISIONAL" in preview["status"]
    reviewed = FMI["score_analysis"](raw, posts, labels, analysis)
    assert math.isnan(reviewed["fmi"])
    assert analysis["comparability_reviewed"] is False
