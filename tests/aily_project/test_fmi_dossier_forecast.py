"""Independent dossier forecast lookup, policy and isolation regression tests."""

import ast
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from aily_project.services.fmi_dossier.excel import finalize, score_rows
from aily_project.services.fmi_dossier.forecast import query_missing
from aily_project.services.fmi_dossier.policy import (
    Policy,
    half_up,
    legacy_uplift,
    uplift,
)

pytestmark = pytest.mark.unit


class Reader:
    def __init__(self, *, writable=False, candidates=None, companies=None):
        self.calls = []
        self.writable = writable
        self.candidates = (
            candidates
            if candidates is not None
            else [
                {
                    "company_code": "OWN",
                    "reported_date": "2026-12-31",
                    "year": 2026,
                    "quarter": "Q4",
                    "type_filter_code": "revenue",
                    "type_filter_value": 100,
                }
            ]
        )
        self.companies = (
            companies
            if companies is not None
            else [
                {
                    "company_code": "OWN",
                    "company_name": "Brand",
                    "company_ticker": "TICK",
                    "company_currency": "EUR",
                }
            ]
        )

    def fetch_data_as_df(self, query, *, bind_params=()):
        self.calls.append((query, bind_params))
        assert query.startswith("SELECT")
        if "current_setting" in query:
            return pd.DataFrame(
                [
                    {
                        "transaction_read_only": "off" if self.writable else "on",
                        "default_transaction_read_only": "on",
                    }
                ]
            )
        if "information_schema.columns" in query:
            return pd.DataFrame(
                [
                    {"table_schema": schema, "table_name": table, "column_name": column}
                    for schema, table, columns in [
                        (
                            "light",
                            "light_companies",
                            [
                                "company_code",
                                "company_name",
                                "company_ticker",
                                "company_currency",
                            ],
                        ),
                        (
                            "ai",
                            "light_financial_statements_forecast",
                            [
                                "company_code",
                                "reported_date",
                                "year",
                                "quarter",
                                "type_filter_code",
                                "type_filter_value",
                            ],
                        ),
                    ]
                    for column in columns
                ]
            )
        return pd.DataFrame(self.candidates if "FROM ai." in query else self.companies)


def source(**changes):
    return {
        "brand_id": "brand",
        "name": "Brand",
        "include": True,
        "light_code": "OWN",
        "ticker": "TICK",
        "financial_subject": "Brand",
        "baseline_revenue": None,
        "baseline_kind": "unadjusted_forecast",
        "baseline_approved": True,
        "baseline_subject": "Brand",
        "baseline_scope": "consolidated",
        "baseline_currency": "EUR",
        "baseline_unit_multiplier": 1,
        "forecast_native_unit_multiplier": 1,
        "forecast_target_label": "Q4 2026",
        "forecast_target_start": "2026-10-01",
        "forecast_target_end": "2026-12-31",
        "score_method": "reported",
        "reported_fmi": 70,
        "ir_score": 60,
        "social_score": 100,
        "trend_score": 50,
        "source_document": "brand.docx",
        **changes,
    }


def query(row, reader):
    return query_missing([row], reader, date(2026, 10, 1), date(2026, 12, 31))


def test_reviewed_forecast_fills_baseline_without_changing_dossier_scores():
    original = source()
    client = Reader()
    rows, audit = query(original, client)
    assert original["baseline_revenue"] is None
    assert rows[0]["baseline_revenue"] == 100
    assert rows[0]["forecast_lookup_status"] == "applied_reviewed_database_baseline"
    assert rows[0]["reported_fmi"] == 70
    assert audit[0]["candidates"][0]["source_row_id"]
    assert client.calls[0][0].startswith("SELECT current_setting")
    assert "information_schema" in client.calls[1][0]
    assert client.calls[-1][1][0] == "OWN"  # code, not the ticker
    calculated, _ = finalize(score_rows(rows, Policy()), Policy())
    assert calculated[0]["raw_fmi"] == 70
    assert calculated[0]["adjusted_forecast"] > 100
    assert calculated[0]["legacy_adjusted_forecast"] > 100
    assert calculated[0]["historical_eligibility"] == "not_verified_historical_replay"


@pytest.mark.parametrize(
    "changes",
    [
        {"baseline_approved": False},
        {"baseline_unit_multiplier": None},
        {"forecast_native_unit_multiplier": None},
        {"baseline_currency": "USD"},
        {"baseline_subject": "Parent"},
        {"baseline_scope": None},
        {"baseline_kind": "already_adjusted"},
        {"forecast_target_start": None},
    ],
)
def test_candidates_do_not_become_baselines_without_matching_review(changes):
    rows, _ = query(source(**changes), Reader())
    assert rows[0]["baseline_revenue"] is None
    assert rows[0]["forecast_candidate_revenue"] == 100
    assert rows[0]["forecast_lookup_status"].startswith("candidate_requires_")
    calculated, _ = finalize(score_rows(rows, Policy()), Policy())
    assert calculated[0]["raw_fmi"] == 70
    assert calculated[0]["adjusted_forecast"] is None


def test_existing_dossier_baselines_are_never_requeried_or_overwritten():
    client = Reader()
    rows, audit = query(source(baseline_revenue=200), client)
    assert rows[0]["baseline_revenue"] == 200
    assert audit == [] and len(client.calls) == 2


def test_unreviewed_existing_amount_is_queried_not_silently_skipped():
    client = Reader()
    rows, audit = query(source(baseline_revenue=200, baseline_approved=False), client)
    assert len(audit) == 1
    assert rows[0]["forecast_candidate_revenue"] == 100
    assert rows[0]["baseline_revenue"] == 200  # source transcription is preserved
    assert rows[0]["forecast_lookup_status"].startswith("candidate_requires_")


def test_native_currency_units_are_not_confused_with_display_millions():
    client = Reader()
    client.candidates[0]["type_filter_value"] = 517275000
    rows, _ = query(source(baseline_unit_multiplier=1000000), client)
    assert rows[0]["baseline_revenue"] == pytest.approx(517.275)
    assert rows[0]["forecast_candidate_revenue"] == 517275000


def test_verified_company_code_takes_precedence_over_ticker_in_code_lookup():
    client = Reader()
    rows, _ = query(source(company_code="OWN", light_code="TICK"), client)
    assert rows[0]["baseline_revenue"] == 100
    assert client.calls[2][1][0] == "OWN"
    assert client.calls[-1][1][0] == "OWN"


def test_writable_session_refused_before_business_or_schema_reads():
    client = Reader(writable=True)
    with pytest.raises(ValueError, match="read-only"):
        query(source(), client)
    assert len(client.calls) == 1


@pytest.mark.parametrize("amount", [0, -1, None, True, float("nan")])
def test_invalid_forecast_amount_never_adjusts(amount):
    client = Reader()
    client.candidates[0]["type_filter_value"] = amount
    rows, _ = query(source(), client)
    assert rows[0]["baseline_revenue"] is None
    assert rows[0]["forecast_lookup_status"] == "invalid_forecast_amount"


def test_duplicate_conflicting_targets_no_summing_and_no_fiscal_fallback():
    client = Reader()
    client.candidates += [{**client.candidates[0], "type_filter_value": 200}]
    rows, _ = query(source(), client)
    assert rows[0]["forecast_lookup_status"] == "conflicting_native_forecast_candidates"
    client.candidates = [{**client.candidates[0], "reported_date": "2027-01-31"}]
    rows, _ = query(source(), client)
    assert rows[0]["forecast_lookup_status"] == "no_exact_native_target_end_forecast"


def test_dossier_service_has_no_automated_fmi_business_imports():
    root = Path(__file__).parents[2]
    for path in (root / "src/aily_project/services/fmi_dossier").glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or not node.module.startswith(
                    "aily_project.services.fmi."
                )
    code = (
        root / "scripts/fashion-momentum-index/notebooks/03_delivery.ipynb"
    ).read_text()
    assert "refresh_dossier_delivery" not in code and "fmi_dossier" not in code
    pipeline = (root / "src/aily_project/services/fmi/tasks/pipeline.py").read_text()
    assert "refresh_dossier_delivery" not in pipeline and "read_reports" not in pipeline


def test_dossier_owned_uplift_math_and_half_up_boundaries():
    policy = Policy()
    assert half_up(84.05) == 84.1
    assert uplift(100, policy) == pytest.approx(0.11)
    assert uplift(70, policy) < uplift(84, policy) < uplift(98, policy)
    assert legacy_uplift(60, policy) == 0
    assert legacy_uplift(70, policy) == pytest.approx(0.05)
