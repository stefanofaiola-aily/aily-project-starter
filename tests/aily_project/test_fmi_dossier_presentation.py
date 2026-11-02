"""Local weighted reference/app planning does not change either score pipeline."""

from copy import deepcopy

import pytest

from aily_project.services.fmi_dossier.excel import fields_for, finalize, score_rows
from aily_project.services.fmi_dossier.policy import Policy
from aily_project.services.fmi_dossier.presentation import (
    app_plan,
    comparison,
    enrich,
    identity,
)

pytestmark = pytest.mark.unit


def input_row(**changes):
    return {
        "brand_id": "burberry",
        "name": "Burberry",
        "include": True,
        "score_method": "reported",
        "reported_fmi": 61.2,
        "ir_score": 34.49,
        "social_score": 100,
        "trend_score": 70,
        "source_document": "burberry.docx",
        "reference_financial_period_start": "2025-03-30",
        "baseline_revenue": 100,
        "baseline_kind": "unadjusted_forecast",
        "baseline_approved": True,
        "baseline_source": "source!N2",
        "baseline_subject": "Burberry",
        "baseline_scope": "brand",
        "baseline_currency": "GBP",
        "baseline_unit_multiplier": 1000000,
        "forecast_target_label": "Calendar Q4 2026",
        "forecast_target_start": "2026-10-01",
        "forecast_target_end": "2026-12-31",
        "source_display_fmi": 87.5,
        "source_projected_forecast": 108.5,
        "latest_growth": 0.0508,
        "latest_gap_pp": -3.1,
        "social_lift_fraction": 0.7988,
        "source_sales_2025": 90,
        **changes,
    }


def calculated(**changes):
    rows, _ = finalize(score_rows([input_row(**changes)], Policy()), Policy())
    return rows[0]


def reference(**changes):
    return {
        "name": "Burberry",
        "raw_fmi": 61.2,
        "display_fmi": 85.2,
        "ir_score": 34.5,
        "social_score": 100,
        "trend_score": 70,
        "company_codes": "burberry",
        "financial_period_start": "2026-04-01",
        **changes,
    }


def test_historical_comparison_precision_and_dynamic_cohort():
    row = calculated()
    result = comparison(row, reference())
    assert (
        result["weighted_reference_match_status"]
        == "same_scores_at_reference_precision"
    )
    assert result["weighted_reference_raw_fmi_difference"] == 0
    assert "cohort" in result["weighted_reference_comparison_reason"]
    assert row["ir_score"] == 34.49


def test_mismatches_and_missingness_are_not_imputed():
    result = comparison(calculated(trend_score=70), reference(trend_score=80))
    assert result["weighted_reference_match_status"] == "different_result"
    assert result["weighted_reference_trend_score_difference"] == -10
    result = comparison(calculated(), reference(raw_fmi=None))
    assert result["weighted_reference_raw_fmi_difference"] is None
    assert "availability" in result["weighted_reference_comparison_reason"]


def test_identity_is_typographic_only_not_parent_fuzzy_mapping():
    assert identity("NORDSTROM") == identity("Nordstrom")
    assert identity("Victoria’s Secret") == identity("Victoria's Secret")
    assert identity("Coach") != identity("Tapestry")


def test_reference_never_overwrites_previous_period_or_current_metrics():
    source = calculated()
    before = deepcopy(source)
    enriched = enrich([source], {"brands": {"burberry": reference()}})[0]
    assert source == before
    assert all(enriched[k] == v for k, v in before.items())
    assert enriched["reference_financial_period_start"] == "2025-03-30"
    assert enriched["weighted_reference_financial_period_start"] == "2026-04-01"
    assert enriched["ir_kpi"] == -3.1
    fields = {f.key: f for f in fields_for([enriched])}
    assert fields["ir_kpi"].unit == "pp"
    assert fields["social_kpi"].unit == "fraction"
    assert fields["trend_kpi"].unit == "fraction"
    assert fields["weighted_reference_ir_score"].type == "number"
    assert fields["weighted_reference_financial_period_start"].type == "date"
    assert not fields["weighted_reference_ir_score"].influences_fmi


def test_source_legacy_reproduces_original_without_double_uplift():
    row = calculated()
    assert row["source_legacy_uplift_fraction"] == pytest.approx(0.085)
    assert row["source_legacy_adjusted_forecast"] == pytest.approx(108.5)
    assert row["source_projection_difference"] == pytest.approx(0)
    assert row["legacy_uplift_fraction"] == pytest.approx(0.0324)
    after = calculated(source_projected_forecast=900)
    assert after["adjusted_forecast"] == row["adjusted_forecast"]
    assert (
        after["source_legacy_adjusted_forecast"]
        == row["source_legacy_adjusted_forecast"]
    )
    assert (
        calculated(baseline_approved=False)["source_legacy_adjusted_forecast"] is None
    )


def test_native_plan_does_not_infer_domain_category_or_company_code():
    row = enrich(
        [calculated(light_code="BRBY.L", ticker="BRBY.L")],
        {"brands": {"burberry": reference()}},
    )[0]
    plan = app_plan([row])
    report = plan["reports"][0]
    assert report["content_json"] is None
    assert report["company_code"] is None
    assert report["reference_company_codes"] == "burberry"
    assert report["content_candidate"]["domain"] is None
    assert report["content_candidate"]["category"] is None
    assert plan["execution"] == "plan" and not plan["live_writes_performed"]
    assert plan["rankings"] == "preserve" and plan["artwork"] == "preserve"


def test_native_metadata_and_approved_copy_allow_local_candidate_only():
    row = enrich(
        [
            calculated(
                app_company_code="burberry",
                app_domain="burberry.com",
                app_category="LUXE",
                app_content_approved=True,
            )
        ],
        {},
    )[0]
    report = app_plan([row])["reports"][0]
    content = report["content_json"]
    assert report["status"] == "local_content_reviewed"
    assert content["schemaVersion"] == 1
    assert content["momentum"]["score"] == row["ir_score"]
    assert content["strength"]["score"] == row["trend_score"]
    assert isinstance(content["momentum"]["kpi"], str)
    assert not content["allowRankingPreview"]
    assert not {"brands", "rankings", "rank", "boardStatus"} & set(content)
    assert report["html"] is None


@pytest.mark.parametrize(
    "changes",
    [
        {"source_sales_2025": None},
        {"app_category": "FAST FOLLOWER"},
        {"social_score": None},
        {"app_content_approved": False},
    ],
)
def test_native_missing_inputs_block_content_without_placeholders(changes):
    params = {
        "app_company_code": "burberry",
        "app_domain": "burberry.com",
        "app_category": "LUXE",
        "app_content_approved": True,
        **changes,
    }
    row = enrich([calculated(**params)], {})[0]
    report = app_plan([row])["reports"][0]
    assert report["status"] == "blocked" and report["content_json"] is None


def test_missing_forecast_keeps_signal_and_truthful_projection():
    row = enrich([calculated(baseline_revenue=None)], {})[0]
    report = app_plan([row])["reports"][0]
    assert report["content_candidate"]["overall"]["score"] == 61.2
    assert (
        report["content_candidate"]["projection"]["displayValue"]
        == "Adjusted forecast unavailable"
    )
