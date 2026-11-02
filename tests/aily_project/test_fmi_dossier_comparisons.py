"""PY forecasts and provisional category boards do not change dossier scoring."""

from copy import deepcopy

import pytest

from aily_project.services.fmi_dossier.excel import fields_for, finalize, score_rows
from aily_project.services.fmi_dossier.policy import Policy
from aily_project.services.fmi_dossier.presentation import leaderboards

pytestmark = pytest.mark.unit


def row(**changes):
    return {
        "brand_id": "brand",
        "name": "Brand",
        "include": True,
        "score_method": "reported",
        "reported_fmi": 70,
        "source_document": "report.docx",
        "company_code": "OWN",
        "leaderboard_category": "LUXE",
        "baseline_revenue": 100,
        "baseline_kind": "unadjusted_forecast",
        "baseline_approved": True,
        "baseline_source": "source.xlsx",
        "baseline_subject": "Brand",
        "baseline_scope": "brand-keyed",
        "baseline_currency": "EUR",
        "baseline_unit_multiplier": 1000000,
        "forecast_target_label": "Calendar Q4 2026",
        "forecast_target_start": "2026-10-01",
        "forecast_target_end": "2026-12-31",
        "prior_year_forecast": 80,
        "prior_year_forecast_status": "comparable_current_snapshot",
        "prior_year_forecast_subject": "Brand",
        "prior_year_forecast_scope": "brand-keyed",
        "prior_year_forecast_currency": "EUR",
        "prior_year_forecast_unit_multiplier": 1000000,
        "prior_year_forecast_company_code": "OWN",
        "prior_year_forecast_source": "ai.light_financial_statements_forecast",
        "prior_year_forecast_reported_date": "2025-12-27",
        "forecast_comparison_reported_date": "2026-12-27",
        "forecast_comparison_baseline_revenue": 100,
        "forecast_comparison_native_year": 2027,
        "forecast_comparison_native_quarter": "Q3",
        "prior_year_forecast_native_year": 2026,
        "prior_year_forecast_native_quarter": "Q3",
        "prior_year_forecast_target_start": "2026-10-01",
        "prior_year_forecast_target_end": "2026-12-31",
        **changes,
    }


def calculate(*inputs):
    return finalize(score_rows(list(inputs), Policy()), Policy())[0]


def test_fiscal_py_forecast_yoy_separate_from_actuals_and_no_double_uplift():
    result = calculate(row())[0]
    assert result["baseline_forecast_vs_py_forecast_yoy"] == pytest.approx(0.25)
    assert result["adjusted_forecast_vs_py_forecast_yoy"] == pytest.approx(
        result["adjusted_forecast"] / 80 - 1
    )
    assert result["legacy_adjusted_forecast_vs_py_forecast_yoy"] == pytest.approx(
        105 / 80 - 1
    )
    assert result["baseline_forecast_yoy"] is None  # No PY actuals were supplied.
    assert result["fmi_increment_vs_py_forecast_pp"] == pytest.approx(
        100 * result["adjustment"] / 80
    )
    changed = calculate(row(prior_year_forecast=40, leaderboard_category="RETAILER"))[0]
    assert changed["raw_fmi"] == result["raw_fmi"]
    assert changed["adjusted_forecast"] == result["adjusted_forecast"]


@pytest.mark.parametrize(
    "changes",
    [
        {"prior_year_forecast": None},
        {"prior_year_forecast": 0},
        {"prior_year_forecast": -1},
        {"prior_year_forecast_status": "unreviewed"},
        {"prior_year_forecast_currency": "USD"},
        {"prior_year_forecast_subject": "Parent"},
        {"prior_year_forecast_company_code": "PARENT"},
        {"prior_year_forecast_scope": "group"},
        {"prior_year_forecast_unit_multiplier": 1},
        {"prior_year_forecast_native_quarter": "Q4"},
        {"prior_year_forecast_native_year": 2025},
        {"prior_year_forecast_reported_date": "2025-09-30"},
        {"forecast_target_end": "2027-01-31"},
        {"baseline_revenue": 110},
        {"baseline_approved": False},
        {"prior_year_forecast_source": None},
    ],
)
def test_incompatible_py_forecast_keeps_score_but_comparison_blank(changes):
    result = calculate(row(**changes))[0]
    assert result["baseline_forecast_vs_py_forecast_yoy"] is None
    assert result["adjusted_forecast_vs_py_forecast_yoy"] is None
    assert result["raw_fmi"] == 70


def test_partial_fmi_keeps_valid_baseline_yoy_but_no_adjusted_yoy():
    result = calculate(row(reported_fmi=None))[0]
    assert result["baseline_forecast_vs_py_forecast_yoy"] == pytest.approx(0.25)
    assert result["adjusted_forecast_vs_py_forecast_yoy"] is None
    assert result["leaderboard_rank"] is None


def test_competition_ties_use_rounded_display_and_only_same_category():
    inputs = [
        row(brand_id="first", reported_fmi=100),
        row(brand_id="tie-a", reported_fmi=50),
        row(brand_id="tie-b", reported_fmi=50.01),
        row(brand_id="fourth", reported_fmi=0),
        row(brand_id="other", reported_fmi=90, leaderboard_category="PREMIUM"),
        row(brand_id="unscored", reported_fmi=None),
        row(brand_id="uncategorized", leaderboard_category=None),
        row(brand_id="unsupported", leaderboard_category="UNASSIGNED_CATEGORY"),
        row(brand_id="excluded", include=False),
    ]
    result = calculate(*inputs)
    assert [r["leaderboard_rank"] for r in result] == [
        1,
        2,
        2,
        4,
        1,
        None,
        None,
        None,
        None,
    ]
    assert result[0]["leaderboard_scored_count"] == 4
    assert result[0]["leaderboard_member_count"] == 5
    assert result[6]["leaderboard_status"] == "missing_category_assignment"
    assert result[7]["leaderboard_status"] == "unsupported_category_assignment"
    original = deepcopy(result)
    boards = leaderboards([r for r in result if r["include"]])
    assert result == original
    assert boards["LUXE"]["scored_count"] == 4
    assert boards["LUXE"]["brands"][-1]["rank"] is None
    moved = calculate(*[{**r, "leaderboard_category": "PREMIUM"} for r in inputs])
    assert moved[0]["leaderboard_scored_count"] == 7


def test_comparison_and_ranking_dictionary_types_units_do_not_influence_fmi():
    fields = {f.key: f for f in fields_for(calculate(row()))}
    assert fields["leaderboard_rank"].type == "number"
    assert fields["leaderboard_rank"].unit == "count"
    assert fields["baseline_forecast_vs_py_forecast_yoy"].unit == "fraction"
    assert fields["fmi_increment_vs_py_forecast_pp"].unit == "pp"
    assert not fields["prior_year_forecast"].influences_fmi
    assert not fields["leaderboard_rank"].influences_fmi


@pytest.mark.parametrize("category", ["LUXE", "PREMIUM", "MASS_MARKET"])
def test_revised_dinner_categories_rank_without_changing_score_or_forecast(category):
    inputs = [
        row(brand_id="first", reported_fmi=90),
        row(brand_id="second", reported_fmi=50),
        row(brand_id="unscored", reported_fmi=None),
    ]
    before = calculate(*inputs)
    after = calculate(*[{**r, "leaderboard_category": category} for r in inputs])
    assert [r["leaderboard_rank"] for r in after] == [1, 2, None]
    assert after[0]["leaderboard_scored_count"] == 2
    assert after[0]["leaderboard_member_count"] == 3
    boards = leaderboards(after)
    assert boards[category]["scored_count"] == 2
    assert boards[category]["member_count"] == 3
    for original, revised in zip(before, after, strict=True):
        for key in ("raw_fmi", "display_fmi", "uplift_fraction", "adjusted_forecast"):
            assert revised[key] == original[key]


def test_new_categories_do_not_remap_unlisted_historical_categories():
    result = calculate(
        row(brand_id="premium", leaderboard_category="PREMIUM"),
        row(brand_id="mass", leaderboard_category="MASS_MARKET"),
        row(brand_id="historical", leaderboard_category="FAST FOLLOWER"),
    )
    assert [r["leaderboard_rank"] for r in result] == [1, 1, None]
    assert all(r["leaderboard_member_count"] == 1 for r in result[:2])
    assert result[2]["leaderboard_status"] == "unsupported_category_assignment"
    assert set(leaderboards(result)) == {"LUXE", "PREMIUM", "MASS_MARKET"}
