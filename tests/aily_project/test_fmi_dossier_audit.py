"""Audit the same service results, without Word parsing or cloud access."""

import json

import pytest

from aily_project.services.fmi_dossier import excel
from aily_project.services.fmi_dossier.audit import traces, write_audit
from aily_project.services.fmi_dossier.policy import Policy

pytestmark = pytest.mark.unit


def source(**changes):
    return {
        "brand_id": "longchamp",
        "name": "Longchamp",
        "include": True,
        "score_method": "reported",
        "reported_fmi": 49.72,
        "ir_score": 52.9959,
        "social_score": 57.41,
        "trend_score": 30,
        "source_document": "dossiers/longchamp.docx",
        "source_score_locator": "Headline and precise formula",
        "latest_revenue": 1038,
        "earlier_revenue": 944,
        "latest_growth": 0.10,
        "currency": "EUR",
        "unit_multiplier": 1000000,
        "scope": "standalone estimated",
        "baseline_median_metric": 1742,
        "current_median_metric": 1871,
        "social_lift_fraction": 0.0741,
        "current_posts": None,
        "baseline_revenue": None,
        "limitations": "PROVISIONAL: peers pending review",
        **changes,
    }


def test_trace_preserves_printed_precision_missingness_and_diagnostic(tmp_path):
    policy = Policy()
    rows, cohort = excel.finalize(excel.score_rows([source()], policy), policy)
    records = traces(rows)
    assert records[0]["groups"]["Results"]["raw_fmi"] == 49.72
    assert records[0]["groups"]["Results"]["weighted_component_fmi"] == pytest.approx(
        49.72095
    )
    assert records[0]["groups"]["Results"][
        "reported_component_difference"
    ] == pytest.approx(0.00095)
    assert records[0]["groups"]["Social"]["current_posts"] is None
    assert records[0]["groups"]["Revenue and peers"]["latest_growth"] == 0.10
    assert records[0]["groups"]["Social"]["social_lift_fraction"] == 0.0741
    assert records[0]["groups"]["Results"]["adjusted_forecast"] is None
    write_audit(records, cohort, policy, tmp_path)
    audit = (tmp_path / "calculation-audit.md").read_text()
    assert "52.9959 × 0.5" in audit and "49.72095" in audit
    assert "preserves the printed dossier headline: 49.72" in audit
    assert "missing_dossier_baseline" in audit and "PROVISIONAL" in audit
    assert "not independently rebuilt" in audit


def test_audit_contains_missing_and_excluded_prospects_and_resolved_policy(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(excel, "write_workbook", lambda *args, **kwargs: None)
    policy = Policy(
        ir_weight=0.4, social_weight=0.4, trend_weight=0.2, uplift_exponent=7
    )
    inputs = [
        source(),
        source(brand_id="excluded", include=False),
        source(
            brand_id="missing",
            reported_fmi=None,
            ir_score=None,
            social_score=None,
            trend_score=None,
            latest_revenue=None,
            current_median_metric=None,
        ),
    ]
    rows, cohort = excel.finalize(excel.score_rows(inputs, policy), policy)
    contract = excel.export_delivery(rows, cohort, policy, tmp_path)
    assert [r["brand_id"] for r in contract["rows"]] == ["longchamp"]
    assert [r["brand_id"] for r in contract["calculation_traces"]] == [
        "longchamp",
        "excluded",
        "missing",
    ]
    assert (
        contract["calculation_traces"][0]["groups"]["Results"]["raw_fmi"]
        == contract["rows"][0]["raw_fmi"]
    )
    audit = (tmp_path / "calculation-audit.md").read_text()
    assert "expm1(7 ×" in audit and "52.9959 × 0.4" in audit
    assert "otherwise 0.03 + 0.08 × expm1(7 ×" in audit
    assert "## Longchamp (missing)" in audit
    assert (
        json.loads((tmp_path / "dossier-calculated-delivery.json").read_text())[
            "calculation_traces"
        ]
        == contract["calculation_traces"]
    )


def test_markdown_source_text_does_not_break_tables(tmp_path):
    policy = Policy()
    rows, cohort = excel.finalize(
        excel.score_rows([source(limitations="a|b\nnext")], policy), policy
    )
    write_audit(traces(rows), cohort, policy, tmp_path)
    assert "a\\|b<br>next" in (tmp_path / "calculation-audit.md").read_text()
