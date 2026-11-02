"""Current-demo forecast periods and typed forecast evidence stay independent of FMI."""

from datetime import date

import pytest

from aily_project.services.fmi_dossier.audit import traces
from aily_project.services.fmi_dossier.excel import fields_for, score_rows
from aily_project.services.fmi_dossier.forecast import select_scenario_forecast
from aily_project.services.fmi_dossier.policy import Policy

pytestmark = pytest.mark.unit


def observation(**changes):
    return {
        "company_code": "BRAND",
        "reported_date": "2026-12-31",
        "year": 2026,
        "quarter": "Q4",
        "type_filter_code": "revenue",
        "type_filter_value": 100,
        "currency": "EUR",
        "unit_multiplier": 1,
        "scope": "company",
        **changes,
    }


def select(*rows):
    return select_scenario_forecast(
        list(rows), date(2026, 10, 1), date(2026, 12, 31), date(2026, 11, 2)
    )


def test_current_calendar_quarter_preserves_native_fiscal_label_and_single_amount():
    result = select(
        observation(year=2027, quarter="Q2", reported_date="2026-12-27"),
        observation(reported_date="2027-01-31", type_filter_value=200),
    )
    assert result["amount"] == 100
    assert result["observations"][0]["quarter"] == "Q2"
    assert result["target_start"] == "2026-10-01"
    assert result["target_end"] == "2026-12-31"


def test_retail_q4_fallback_is_labelled_and_past_quarters_are_not_used():
    result = select(
        observation(reported_date="2027-02-07"), observation(reported_date="2026-06-30")
    )
    assert result["method"] == "native_fiscal_q4_proxy"
    assert result["target_start"] == "2026-11-01"
    assert result["target_end"] == "2027-02-07"
    assert "not_verified_native" in result["period_start_basis"]


def test_duplicate_equivalent_values_are_retained_once_and_conflicts_block():
    assert select(observation(), observation())["amount"] == 100
    assert (
        select(observation(), observation(type_filter_value=101))["status"]
        == "conflicting_current_quarter_forecasts"
    )


def test_complete_monthly_fallback_is_three_months_not_quarter_phasing():
    rows = [
        observation(
            grain="monthly", quarter=None, reported_date=day, type_filter_value=i * 100
        )
        for i, day in enumerate(["2026-11-30", "2026-12-31", "2027-01-31"], 1)
    ]
    result = select(*rows)
    assert result["amount"] == 600
    assert result["method"] == "current_and_next_two_complete_months"
    assert result["target_start"] == "2026-11-01"
    assert result["target_end"] == "2027-01-31"
    assert select(*rows[:2])["status"] == "missing_or_conflicting_three_month_forecast"
    rows[1]["currency"] = "USD"
    assert select(*rows)["status"] == "incompatible_monthly_forecast_basis"


@pytest.mark.parametrize("amount", [None, True, 0, -1, float("nan")])
def test_invalid_forecast_values_are_not_replaced_with_dummy_baselines(amount):
    assert "amount" not in select(observation(type_filter_value=amount))


def test_excel_forecast_evidence_decodes_to_arrays_without_changing_source_scores():
    source = {
        "brand_id": "brand",
        "name": "Brand",
        "score_method": "reported",
        "reported_fmi": 49.72,
        "ir_score": 52.9959,
        "source_document": "report.docx",
        "forecast_lookup_candidates": '[{"type_filter_value":100}]',
    }
    result = score_rows([source], Policy())[0]
    assert result["raw_fmi"] == 49.72 and result["ir_score"] == 52.9959
    assert result["forecast_lookup_candidates"] == [{"type_filter_value": 100}]
    assert isinstance(source["forecast_lookup_candidates"], str)
    with pytest.raises(ValueError, match="source-record arrays"):
        score_rows([{**source, "forecast_lookup_candidates": "[100]"}], Policy())


def test_forecast_ticker_alias_preserves_app_identity_and_audit_source_key():
    source = {
        "brand_id": "hermes",
        "name": "Hermès",
        "company_code": "HERMES",
        "baseline_company_code": "HERMES",
        "forecast_native_company_code": "RMS.PA",
        "score_method": "reported",
        "reported_fmi": 65,
        "source_document": "hermes.docx",
        "forecast_lookup_candidates": '[{"company_code":"RMS.PA"}]',
    }
    row = score_rows([source], Policy())[0]
    assert row["company_code"] == row["baseline_company_code"] == "HERMES"
    assert row["raw_fmi"] == 65
    evidence = traces([row])[0]["groups"]["Forecast evidence"]
    assert evidence["forecast_native_company_code"] == "RMS.PA"
    field = next(
        f for f in fields_for([row]) if f.key == "forecast_native_company_code"
    )
    assert field.type == "string"
    assert "ticker alias" in field.derivation
