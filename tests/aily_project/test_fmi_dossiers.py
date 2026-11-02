"""Archived references are not production measurements or interchangeable scores."""

import pytest

from aily_project.services.fmi import dossiers
from aily_project.services.fmi.policy import Policy

pytestmark = pytest.mark.unit


def project(monkeypatch, tmp_path, intro, tables):
    path = tmp_path / "report.docx"
    path.write_bytes(b"immutable archive fixture")
    monkeypatch.setattr(
        dossiers, "report_content", lambda _: (["Brand", intro], tables)
    )
    return dossiers.project_report(path)


def test_report_not_old_summary_is_authority(monkeypatch, tmp_path):
    row = project(
        monkeypatch,
        tmp_path,
        "Spring 2026 scores 68.2/100.",
        [
            [
                ["Collection", "Social", "Momentum", "Strength", "Overall"],
                ["Fall 2025", "24.5", "100", "70", "71.4/100"],
                ["Spring 2026", "13.9", "100", "70", "68.2/100"],
            ]
        ],
    )
    assert row["dossier_headline_fmi"] == 68.2
    assert row["dossier_component_cycle"] == "Spring 2026"
    assert row["dossier_arithmetic_status"] == "matches_printed_precision"
    assert len(row["dossier_source_sha256"]) == 64


def test_partial_social_is_not_overall(monkeypatch, tmp_path):
    row = project(
        monkeypatch,
        tmp_path,
        "Social subscore is 0/100. Financial momentum and "
        "the overall score remain unavailable.",
        [[["Overall", "Result"], ["Social subscore", "0/100"]]],
    )
    assert row["dossier_headline_fmi"] is None


def test_strength_subscore_not_conditional_overall(monkeypatch, tmp_path):
    row = project(
        monkeypatch,
        tmp_path,
        "Strength is Fallback, 30/100. Weighted method gives "
        "conditional overall score of 30.2/100.",
        [],
    )
    assert row["dossier_headline_fmi"] == 30.2


def test_parent_comments_proxy_is_preserved(monkeypatch, tmp_path):
    row = project(
        monkeypatch,
        tmp_path,
        "Parent-company and comments proxy is 42.3/100. "
        "Direct overall remains unavailable.",
        [],
    )
    assert row["dossier_headline_fmi"] == 42.3
    assert "comments" in row["dossier_method_limitations"]


def test_normalized_percentile_not_silently_raw(monkeypatch, tmp_path):
    row = project(
        monkeypatch,
        tmp_path,
        "Normalized proxy score is 47.0/100.",
        [
            [
                ["Component", "Input", "Percentile"],
                ["Financial momentum", "0.08 pp", "60"],
                ["Social", "-15%", "50"],
                ["Strength", "30", "10"],
            ]
        ],
    )
    assert row["dossier_original_raw_fmi"] is None
    assert row["dossier_component_sum"] == 47
    assert row["dossier_score_basis"] == "component_percentile_normalized"


def test_arithmetic_mismatch_disclosed(monkeypatch, tmp_path):
    row = project(
        monkeypatch,
        tmp_path,
        "Overall score is 70/100.",
        [
            [
                ["Component", "Subscore"],
                ["Momentum", "100"],
                ["Social", "100"],
                ["Strength", "100"],
            ]
        ],
    )
    assert (
        row["dossier_arithmetic_status"] == "printed_components_do_not_match_headline"
    )
    assert row["dossier_headline_fmi"] == 70


@pytest.mark.parametrize("code,expected", [("RL", True), ("PARENT", False)])
def test_dossier_uplift_is_new_scope_checked_scenario(code, expected):
    reference = {
        "brand_id": "ralph-lauren",
        "dossier_headline_fmi": 70,
        "dossier_original_raw_fmi": 70,
    }
    current = {
        "brand_id": "ralph-lauren",
        "light_code": code,
        "baseline_revenue": 100,
        "raw_fmi": 80,
    }
    row = dossiers.scenario_rows([reference], [current], Policy())[0]
    assert row["dossier_headline_fmi"] == 70
    assert row["dossier_scenario_display_fmi"] == 84
    assert (row.get("baseline_revenue") is not None) == expected
    if expected:
        assert row["dossier_scenario_legacy_adjusted_forecast"] == pytest.approx(105)
    assert "NOT original" in row["dossier_scenario_notice"]


def test_dossier_dictionary_and_flat_row_types():
    row = {
        "brand_id": "b",
        "name": "Brand",
        "dossier_headline_fmi": 65.5,
        "dossier_scenario_uplift_fraction": 0.02,
        "historical_summary_conflict": True,
    }
    spec = dossiers.payload([row])["sheets"][0]
    fields = {f["field_key"]: f for f in spec["fields"]}
    assert fields["dossier_scenario_uplift_fraction"]["unit"] == "fraction"
    assert fields["historical_summary_conflict"]["type"] == "boolean"
    assert set(spec["rows"][0]) == set(spec["keys"])
    assert not any(f["influences_fmi"] for f in spec["fields"])


def test_missing_dossiers_do_not_create_neutral_scores():
    assert dossiers.scenario_rows([], [], Policy()) == []


def test_percentile_headline_cannot_enter_raw_rescaling_cohort():
    reference = {
        "brand_id": "lvmh",
        "dossier_headline_fmi": 28,
        "dossier_original_raw_fmi": None,
    }
    row = dossiers.scenario_rows([reference], [], Policy())[0]
    assert row["dossier_headline_fmi"] == 28
    assert row["dossier_scenario_display_fmi"] is None
    assert row["dossier_scenario_uplift_fraction"] is None


def test_component_comparison_reconciles_headline_and_preserves_reference():
    reference = {
        "brand_id": "brand",
        "dossier_headline_fmi": 61.2,
        "dossier_original_raw_fmi": 61.2,
        "dossier_ir_score": 34.5,
        "dossier_social_score": 100,
        "dossier_trend_score": 70,
        "dossier_component_sum": 61.25,
    }
    current = {
        "brand_id": "brand",
        "ir_score": 10,
        "social_score": 80,
        "trend_score": 50,
        "raw_fmi": 39,
    }
    row = dossiers.scenario_rows([reference], [current], Policy())[0]
    assert all(row[key] == value for key, value in reference.items())
    assert row["current_ir_score"] == 10
    assert row["comparison_ir_difference"] == -24.5
    assert row["comparison_ir_fmi_impact"] == -12.25
    assert row["comparison_social_fmi_impact"] == -6
    assert row["comparison_trend_fmi_impact"] == -4
    assert (
        row["comparison_components_fmi_difference"]
        + row["comparison_headline_rounding_difference"]
    ) == pytest.approx(row["comparison_headline_difference"])
    assert reference["dossier_component_sum"] == 61.25


def test_missing_current_component_never_imputes_zero():
    row = dossiers.component_comparison(
        {"dossier_ir_score": 100, "dossier_social_score": 80},
        {"ir_score": 0, "social_score": None},
        Policy(),
    )
    assert row["current_ir_score"] == 0
    assert row["comparison_ir_fmi_impact"] == -50
    assert row["current_social_score"] is None
    assert row["comparison_social_difference"] is None
    assert row["comparison_social_fmi_impact"] is None
    assert row["comparison_components_fmi_difference"] is None
    assert row["comparison_component_status"].startswith("partial")
    spec = dossiers.payload([row])["sheets"][0]
    fields = {f["field_key"]: f for f in spec["fields"]}
    assert fields["current_social_score"]["type"] == "number"
    assert fields["comparison_social_fmi_impact"]["unit"] == "score_points"


def test_percentile_component_comparison_does_not_claim_original_raw_gap():
    row = dossiers.scenario_rows(
        [
            {
                "brand_id": "fendi",
                "dossier_headline_fmi": 47,
                "dossier_original_raw_fmi": 47.3,
                "dossier_ir_score": 60,
                "dossier_social_score": 50,
                "dossier_trend_score": 10,
                "dossier_component_sum": 47,
            }
        ],
        [
            {
                "brand_id": "fendi",
                "raw_fmi": 60,
                "ir_score": 60,
                "social_score": 60,
                "trend_score": 60,
            }
        ],
        Policy(),
    )[0]
    assert row["comparison_components_fmi_difference"] == 13
    assert row["comparison_raw_difference"] == pytest.approx(12.7)
    assert "not_like_for_like" in row["comparison_component_status"]


def test_component_impact_uses_current_policy_weights():
    row = dossiers.component_comparison(
        {"dossier_ir_score": 100, "dossier_social_score": 0, "dossier_trend_score": 0},
        {"ir_score": 100, "social_score": 0, "trend_score": 0, "raw_fmi": 40},
        Policy(ir_weight=0.4, social_weight=0.4),
    )
    assert row["comparison_ir_difference"] == 0
    assert row["comparison_ir_fmi_impact"] == -10
    assert row["comparison_components_fmi_difference"] == -10
