"""Presentation export does not change dossier scores, cohort or source snapshots."""

import json
from copy import deepcopy

import pytest
from click.testing import CliRunner

from aily_project.services.fmi_dossier import html_delivery as service

pytestmark = pytest.mark.unit


def contract(**changes):
    return {
        "schema_version": "fmi-dossier-delivery-v2",
        "fields": [],
        "rows": [
            {
                "brand_id": "fendi",
                "name": "Fendi",
                "raw_fmi": 47.3,
                "display_fmi": 81.6,
                "ir_score": 50.4,
                "social_score": 53.6,
                "trend_score": 30,
                "company_code": "FENDI",
                "email_domains": "fendi.com; lvmh.com",
                "leaderboard_category": "LUXE",
                "leaderboard_rank": 7,
                "one_core_insight": "Existing overall insight",
                "ir_insight": "Existing IR insight",
                "social_insight": "Existing Social insight",
                "trend_insight": "Existing Strength insight",
                "source_q4_vs_baseline_2024": 0,
                "source_q4_vs_baseline_2025": None,
                "source_q4_vs_baseline_2026": 0.0732,
                "source_q4_sales_yoy_2024": -0.029166666666666674,
                "source_q4_sales_yoy_2025": -0.03433476394849788,
                "source_social_2024": 0.3834,
                "source_social_2025": None,
                "source_insights_descriptive": "Stale -1.3% forecast narrative",
                "forecast_target_label": "Calendar Q4 2026",
                "baseline_revenue": 517.275,
                "uplift_fraction": 0.08728054897478865,
                "adjusted_forecast": 562.4230459709337,
                "prior_year_forecast": 562.5,
                "adjusted_forecast_vs_py_forecast_yoy": -0.00013680716278452465,
                "baseline_forecast_vs_py_forecast_yoy": -0.0804,
                "baseline_currency": "EUR",
                "baseline_unit_multiplier": 1000000,
                "financial_subject": "LVMH Fashion and Leather Goods",
                "baseline_subject": "Fendi",
                **changes,
            }
        ],
    }


def exported(**changes):
    return service.build_payload(contract(**changes))["sheets"][0]


def test_score_insight_identity_category_and_social_history_are_unchanged():
    source = contract()
    before = deepcopy(source)
    result = service.build_payload(source)["sheets"][0]
    allowed_changes = {
        "source_q4_vs_baseline_2024",
        "source_q4_vs_baseline_2025",
        "source_q4_vs_baseline_2026",
        "source_insights_descriptive",
        "source_insights_statistics",
    }
    for key, _ in service.PRESENTATION_COLUMNS:
        if key not in allowed_changes:
            assert result["rows"][0][key] == source["rows"][0].get(key)
    assert source == before
    assert result["rows"][0]["source_q4_vs_baseline_2024"] == pytest.approx(
        -0.029166666666666674
    )
    assert result["rows"][0]["source_q4_vs_baseline_2025"] == pytest.approx(
        -0.03433476394849788
    )


def test_fendi_headline_is_new_py_comparison_not_uplift():
    spec = exported()
    row = spec["rows"][0]
    assert row["source_q4_vs_baseline_2026"] == pytest.approx(-0.00013680716278452465)
    assert row["uplift_fraction"] == pytest.approx(0.08728054897478865)
    assert "Q4 vs Baseline ’26 (%)" in spec["labels"]
    assert "-0.01%" in row["source_insights_descriptive"]
    assert "+8.73%" in row["source_insights_descriptive"]
    assert "-1.3%" not in row["source_insights_descriptive"]
    assert "EUR 562.423 million" in row["source_insights_statistics"]
    assert "-3.43%" in row["source_insights_descriptive"]
    assert len(row["source_insights_descriptive"]) < 350
    assert "baseline EUR" not in row["source_insights_descriptive"]


@pytest.mark.parametrize("missing", [None, False, float("nan"), float("inf")])
def test_missing_new_projection_never_falls_back_to_legacy(missing):
    row = exported(adjusted_forecast_vs_py_forecast_yoy=missing)["rows"][0]
    assert row["source_q4_vs_baseline_2026"] is None
    assert "unavailable" in row["source_insights_descriptive"]
    assert row["raw_fmi"] == 47.3


def test_zero_projection_is_present_not_missing():
    row = exported(adjusted_forecast_vs_py_forecast_yoy=0)["rows"][0]
    assert row["source_q4_vs_baseline_2026"] == 0
    assert "+0.00%" in row["source_insights_descriptive"]


def test_parent_proxy_scope_and_mixed_history_are_explicit():
    row = exported(baseline_is_parent_proxy=True)["rows"][0]
    assert "parent/group proxy" in row["revenue_methodology"]
    assert "not actual sales" in row["source_insights_statistics"]
    assert "source Q4 sales YoY" in row["historical_comparison_basis"]
    assert "not actual sales" in row["historical_comparison_basis"]
    row = exported()["rows"][0]
    assert "hybrid/proxy scenario" in row["revenue_methodology"]


def test_categories_and_missing_app_keys_are_not_invented():
    row = exported(leaderboard_category="PREMIUM", company_code=None)["rows"][0]
    assert row["leaderboard_category"] == "PREMIUM"
    assert row["company_code"] is None


def test_header_contract_is_unique_small_and_units_are_preserved():
    source = contract()
    source["fields"] = [
        {"field_key": "ir_kpi", "type": "number", "unit": "pp"},
        {"field_key": "social_kpi", "type": "number", "unit": "fraction"},
    ]
    result = service.build_payload(source)["sheets"][0]
    assert len(result["labels"]) == len(set(result["labels"])) == 50
    fields = {f["field_key"]: f for f in result["fields"]}
    assert fields["ir_kpi"]["unit"] == "pp"
    assert fields["social_kpi"]["unit"] == "fraction"
    assert fields["source_q4_vs_baseline_2026"]["source_fields"] == [
        "adjusted_forecast_vs_py_forecast_yoy"
    ]
    assert "not a legacy uplift" in fields["source_q4_vs_baseline_2026"]["derivation"]
    assert (
        fields["source_insights_descriptive"]["source_kind"] == "presentation_mapping"
    )
    for year in (2024, 2025):
        field = fields[f"source_q4_vs_baseline_{year}"]
        assert field["source_fields"] == [f"source_q4_sales_yoy_{year}"]
        assert field["unit"] == "fraction"
        assert "No fallback" in field["derivation"]


@pytest.mark.parametrize("missing", [None, False, float("nan"), float("inf")])
def test_missing_historical_yoy_never_uses_baseline_variance(missing):
    row = exported(source_q4_sales_yoy_2024=missing, source_q4_sales_yoy_2025=missing)[
        "rows"
    ][0]
    assert row["source_q4_vs_baseline_2024"] is None
    assert row["source_q4_vs_baseline_2025"] is None
    assert "Q4 sales YoY" not in row["source_insights_descriptive"]


def test_zero_historical_yoy_and_sparse_social_are_not_lost_or_invented():
    row = exported(
        source_q4_sales_yoy_2025=0,
        source_social_2024=None,
        source_social_2025=0,
        source_social_2026=-0.4161,
    )["rows"][0]
    assert row["source_q4_vs_baseline_2025"] == 0
    assert "Q4 sales YoY was +0.00% in 2025" in row["source_insights_descriptive"]
    assert "+0.00% (2025), -41.61% (2026)" in row["source_insights_descriptive"]
    assert "(2024)" not in row["source_insights_descriptive"]


def test_summary_regenerates_from_final_values_not_old_source_narrative():
    row = exported(
        source_social_2025=0.0362,
        source_social_2026=-0.4161,
        adjusted_forecast_vs_py_forecast_yoy=0.05,
    )["rows"][0]
    assert "+5.00% vs PY forecast" in row["source_insights_descriptive"]
    assert "-0.01%" not in row["source_insights_descriptive"]
    assert "-1.3%" not in row["source_insights_descriptive"]
    assert "Source social lift" in row["source_insights_descriptive"]


def test_wrong_source_contract_is_rejected():
    with pytest.raises(ValueError, match="completed"):
        service.build_payload({"schema_version": "automated-fmi"})


def test_cli_uses_presentation_writer_only(tmp_path, monkeypatch):
    source = tmp_path / "source.json"
    source.write_text(json.dumps(contract()))
    calls = []
    monkeypatch.setattr(
        service, "write_workbook", lambda *a, **kw: calls.append((a, kw))
    )
    output = tmp_path / "html.xlsx"
    result = CliRunner().invoke(
        service.fmi_dossier_html,
        ["--source", str(source), "--output", str(output), "--previews"],
    )
    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    assert calls[0][1] == {"previews": True, "template": "html_workbook.mjs"}
    assert "1 brands; 50 columns; 1 new PY-forecast comparisons" in result.output
    exported_json = json.loads(output.with_suffix(".json").read_text())
    assert exported_json["schema_version"] == "fmi-dossier-html-v1"
    assert exported_json["rows"] == calls[0][0][0]["sheets"][0]["rows"]
    assert exported_json["fields"] == service.clean(
        calls[0][0][0]["sheets"][0]["fields"]
    )
