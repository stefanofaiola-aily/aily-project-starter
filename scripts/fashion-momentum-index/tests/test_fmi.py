"""FMI arithmetic and missing-data behavior; no cloud or database access."""

import math
import runpy
from pathlib import Path

import pandas as pd
import pytest

FMI = runpy.run_path(str(Path(__file__).parents[1] / "fmi.py"))
pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "score,expected",
    [
        (0, "Low"),
        (39.999, "Low"),
        (40, "Neutral"),
        (59.999, "Neutral"),
        (60, "Medium"),
        (69.999, "Medium"),
        (70, "High"),
        (100, "High"),
        (math.nan, "Unavailable"),
        (-1, "Unavailable"),
        (101, "Unavailable"),
    ],
)
def test_band_uses_unrounded_boundaries(score: float, expected: str) -> None:
    assert FMI["band"](score) == expected


@pytest.mark.parametrize(
    "latest,earlier,expected",
    [
        (3, -1, 70),
        (6, 10, 30),
        (7, 5, 80),
        (5, 7, 80),
        (2, 0, 50),
        (-2, 0, 50),
        (5, 5, 80),
        (1, 1, 50),
    ],
)
def test_trend_applies_ordered_rules_and_exact_boundaries(
    latest: float,
    earlier: float,
    expected: float,
) -> None:
    assert FMI["trend_score"](latest, earlier)[0] == expected


@pytest.mark.parametrize(
    "score,uplift",
    [
        (40, 0),
        (60, 0),
        (60.1, 3.02),
        (70, 5),
        (70.5, 5.1),
        (80, 7),
        (85, 8),
        (90, 9),
        (100, 11),
    ],
)
def test_scenario_matches_handover(score: float, uplift: float) -> None:
    result = FMI["sales_scenario"](score, 100, 102)
    assert result["uplift_pct"] == pytest.approx(uplift)
    assert result["adjusted_forecast"] == pytest.approx(100 + uplift)
    assert result["forecast_yoy_pct"] == pytest.approx(
        ((100 + uplift) / 102 - 1) * 100,
    )


@pytest.mark.parametrize(
    "score,baseline",
    [
        (math.nan, 100),
        (101, 100),
        (70, math.nan),
        (70, 0),
    ],
)
def test_scenario_refuses_invalid_inputs(score: float, baseline: float) -> None:
    assert FMI["sales_scenario"](score, baseline, 102) == {}


def test_full_worked_example_matches_document() -> None:
    financials, posts, labels, analysis = FMI["demo_inputs"]()
    result = FMI["score_analysis"](financials, posts, labels, analysis)
    assert result["brand_growth_pct"] == pytest.approx(8)
    assert result["peer_median_growth_pct"] == pytest.approx(5)
    assert result["earlier_relative_pp"] == pytest.approx(-1)
    assert result["ir_score"] == pytest.approx(65)
    assert result["social_score"] == pytest.approx(80)
    assert result["trend_score"] == 70
    assert result["fmi"] == pytest.approx(70.5)
    assert result["classification"] == "High"
    assert result["adjusted_forecast"] == pytest.approx(105100000)
    assert not result["gaps"]


def test_missing_peer_keeps_social_but_no_full_fmi() -> None:
    financials, posts, labels, analysis = FMI["demo_inputs"]()
    financials = financials.loc[financials["entity"].ne(analysis["peer_2"])]
    result = FMI["score_analysis"](financials, posts, labels, analysis)
    assert result["social_score"] == pytest.approx(80)
    assert math.isnan(result["fmi"])
    assert "select exactly one financial row" in result["gaps"]
    assert "adjusted_forecast" not in result


def test_zero_social_baseline_is_unavailable_not_neutral() -> None:
    financials, posts, labels, analysis = FMI["demo_inputs"]()
    posts.loc[posts["date_posted"].str.startswith("2024"), "likes"] = 0
    result = FMI["score_analysis"](financials, posts, labels, analysis)
    assert math.isnan(result["social_score"])
    assert math.isnan(result["fmi"])
    assert "Baseline median is zero" in result["gaps"]


def test_zero_current_likes_are_valid() -> None:
    _, posts, labels, analysis = FMI["demo_inputs"]()
    posts.loc[posts["date_posted"].str.startswith("2025"), "likes"] = 0
    result = FMI["social_component"](posts, labels, analysis)
    assert result["social_score"] == 0
    assert result["current_post_count"] == 5


def test_duplicate_and_future_capture_do_not_bias_median() -> None:
    _, posts, labels, analysis = FMI["demo_inputs"]()
    duplicate = posts.iloc[[5]].copy()
    duplicate["likes"] = 999999
    duplicate["crawled_at"] = "2026-11-01T12:00:00Z"
    posts = pd.concat([posts, duplicate, posts.iloc[[5]]], ignore_index=True)
    result = FMI["social_component"](posts, labels, analysis)
    assert result["social_score"] == pytest.approx(80)
    assert result["current_post_count"] == 5


def test_point_in_time_excludes_unknown_capture_dates() -> None:
    _, posts, labels, analysis = FMI["demo_inputs"]()
    posts.loc[posts["date_posted"].str.startswith("2025"), "crawled_at"] = None
    with pytest.raises(ValueError, match="too sparse"):
        FMI["social_component"](posts, labels, analysis)
    analysis["point_in_time"] = False
    assert FMI["social_component"](posts, labels, analysis)[
        "social_score"
    ] == pytest.approx(80)


def test_missing_baseline_does_not_erase_valid_fmi() -> None:
    financials, posts, labels, analysis = FMI["demo_inputs"]()
    financials = financials.loc[financials["period_role"].ne("target")]
    result = FMI["score_analysis"](financials, posts, labels, analysis)
    assert result["fmi"] == pytest.approx(70.5)
    assert "adjusted_forecast" not in result
    assert "sales scenario unavailable" in result["gaps"]


def test_forecast_yoy_requires_same_quarter_scope() -> None:
    financials, posts, labels, analysis = FMI["demo_inputs"]()
    financials.loc[financials["period_role"].eq("last_year_target"), "scope"] = (
        "segment"
    )
    result = FMI["score_analysis"](financials, posts, labels, analysis)
    assert result["adjusted_forecast"] == pytest.approx(105100000)
    assert math.isnan(result["forecast_yoy_pct"])
    assert "forecast YoY unavailable" in result["gaps"]


def test_mismatched_baseline_currency_blocks_sales_scenario() -> None:
    financials, posts, labels, analysis = FMI["demo_inputs"]()
    financials.loc[financials["period_role"].eq("target"), "currency"] = "USD"
    result = FMI["score_analysis"](financials, posts, labels, analysis)
    assert result["fmi"] == pytest.approx(70.5)
    assert "adjusted_forecast" not in result


def test_future_forecast_version_is_not_used() -> None:
    financials, posts, labels, analysis = FMI["demo_inputs"]()
    financials.loc[financials["period_role"].eq("target"), "published_at"] = (
        "2026-11-01"
    )
    result = FMI["score_analysis"](financials, posts, labels, analysis)
    assert "published after cutoff" in result["gaps"]
    assert "adjusted_forecast" not in result


def test_financial_growth_zero_denominator_is_unavailable() -> None:
    financials, posts, labels, analysis = FMI["demo_inputs"]()
    financials.loc[financials["period_role"].eq("oldest"), "amount"] = 0
    result = FMI["score_analysis"](financials, posts, labels, analysis)
    assert math.isnan(result["fmi"])
    assert "denominator is zero" in result["gaps"]


def test_two_distinct_peers_are_required() -> None:
    financials, posts, labels, analysis = FMI["demo_inputs"]()
    analysis["peer_2"] = analysis["peer_1"]
    result = FMI["score_analysis"](financials, posts, labels, analysis)
    assert math.isnan(result["fmi"])
    assert "two distinct peers" in result["gaps"]


def test_show_windows_and_manual_collection_filter() -> None:
    _, _, _, analysis = FMI["demo_inputs"]()
    analysis.update({"route": "show", "show_date": "2025-06-01", "min_posts": 1})
    rows = [
        ("pre", "2025-05-31T12:00:00Z", 100),
        ("show", "2025-06-01T12:00:00Z", 130),
        ("last_show_day", "2025-06-08T12:00:00Z", 130),
        ("not_collection", "2025-06-05T12:00:00Z", 100000),
        ("post", "2025-06-09T12:00:00Z", 100),
        ("last_baseline_day", "2025-07-08T12:00:00Z", 100),
        ("outside", "2025-07-09T12:00:00Z", 100000),
    ]
    posts = pd.DataFrame(
        [
            {
                "handle": "example_brand",
                "post_key": key,
                "date_posted": date,
                "likes": likes,
                "crawled_at": "2025-08-01T00:00:00Z",
                "url": "",
            }
            for key, date, likes in rows
        ]
    )
    labels = pd.DataFrame(
        [
            {"handle": "example_brand", "post_key": key, "collection_related": include}
            for key, include in [
                ("show", True),
                ("last_show_day", True),
                ("not_collection", False),
            ]
        ]
    )
    result = FMI["social_component"](posts, labels, analysis)
    assert result["current_post_count"] == 2
    assert result["baseline_post_count"] == 3
    assert result["social_score"] == pytest.approx(80)
    with pytest.raises(ValueError, match="Classify all show-week"):
        FMI["social_component"](posts, labels.iloc[:2], analysis)


def test_social_annual_partial_vs_full_year_is_refused() -> None:
    _, posts, labels, analysis = FMI["demo_inputs"]()
    analysis["social_current_end"] = "2025-06-30"
    with pytest.raises(ValueError, match="equivalent social coverage"):
        FMI["social_component"](posts, labels, analysis)


def test_identifiers_reject_sql_injection() -> None:
    with pytest.raises(ValueError, match="Invalid SQL identifier"):
        FMI["quote_identifier"]("company; DROP TABLE x")
    assert FMI["quote_identifier"]("company_code") == '"company_code"'


def test_writable_connection_is_refused() -> None:
    class WritableDB:
        def execute_and_fetch(self, _: str) -> list[dict[str, str]]:
            return [{"read_only": "off"}]

    with pytest.raises(RuntimeError, match="writable"):
        FMI["require_read_only"](WritableDB())


def test_financial_selection_never_sums_versions() -> None:
    raw = pd.DataFrame(
        [
            {"entity": "brand", "source_row_id": "v1", "amount": 100, "scope": "group"},
            {"entity": "brand", "source_row_id": "v2", "amount": 110, "scope": "group"},
        ]
    )
    selected = pd.DataFrame(
        [
            {"entity": "brand", "period_role": "target", "source_row_id": "v1"},
        ]
    )
    result = FMI["select_financials"](raw, selected, pd.DataFrame())
    assert result.iloc[0]["amount"] == 100
    with pytest.raises(ValueError, match="one financial row"):
        FMI["select_financials"](raw, pd.concat([selected, selected]), pd.DataFrame())


def test_proxy_label_is_required() -> None:
    financials, posts, labels, analysis = FMI["demo_inputs"]()
    analysis["financial_proxy"] = True
    result = FMI["score_analysis"](financials, posts, labels, analysis)
    assert math.isnan(result["fmi"])
    assert "Proxy label is required" in result["gaps"]


def test_mixed_timestamp_formats_are_parsed_without_dropping_posts() -> None:
    _, posts, labels, analysis = FMI["demo_inputs"]()
    posts.loc[0, "date_posted"] = "2024-06-01 12:00:00+00:00"
    posts.loc[5, "crawled_at"] = "2025-06-02"
    result = FMI["social_component"](posts, labels, analysis)
    assert result["current_post_count"] == 5
    assert result["baseline_post_count"] == 5


def test_export_social_uses_latest_capture_before_exact_cutoff() -> None:
    calls = []
    captures = [
        {
            "handle": "brand",
            "post_key": "a",
            "date_posted": "2025-06-01",
            "likes": likes,
            "crawled_at": captured,
            "url": "",
        }
        for likes, captured in [
            (130, "2026-10-28 09:00:00+00:00"),
            (140, "2026-10-28T10:00:00Z"),
            (9999, "2026-10-28T18:00:00Z"),
            (10000, None),
        ]
    ]

    class FakeDB:
        def execute_and_fetch(self, query: str, **kwargs: object) -> list[dict]:
            calls.append((query, kwargs))
            if "current_setting" in query:
                return [{"read_only": "on"}]
            if "information_schema.columns" in query:
                return [
                    {"column_name": col}
                    for col in [
                        "user_posted",
                        "post_id",
                        "shortcode",
                        "url",
                        "date_posted",
                        "likes",
                        "crawled_at",
                    ]
                ]
            return captures

    handle = "brand' OR 1=1 --"
    result = FMI["export_social"](
        FakeDB(),
        [handle],
        "2025-01-01",
        "2025-12-31",
        "2026-10-28T12:00:00Z",
    )
    assert len(result) == 1
    assert result.iloc[0]["likes"] == 140
    query, options = calls[-1]
    assert handle not in query
    assert options["bind_params"][0] == handle.lower()
    with pytest.raises(ValueError, match="exceeds row limit"):
        FMI["export_social"](
            FakeDB(),
            ["brand"],
            "2025-01-01",
            "2025-12-31",
            "2026-10-28T12:00:00Z",
            limit=2,
        )
