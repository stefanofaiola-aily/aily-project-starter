"""Flat delivery, dinner reconciliation and non-scoring source context."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from aily_project.services.fmi.configuration import event_reconciliation
from aily_project.services.fmi.flat_delivery import (
    flat_payload,
    observed_revenue,
    observed_target_forecast,
)
from aily_project.services.fmi.models import FMIResult, Inputs, Snapshot
from aily_project.services.fmi.policy import Policy
from aily_project.services.fmi.run_records import monthly_context
from aily_project.services.fmi.tasks.pipeline import deliver, delivery_task, save_json

pytestmark = pytest.mark.unit


def source_row(**changes):
    return {
        "source_relation": "normalized.v_finance_financial_statements",
        "source_row_id": "native-row",
        "symbol": "PRIVATE",
        "date": "2026-06-30",
        "period_label": "Shared calendar 2026 Q2",
        "metric": "revenue",
        "kind": "actual",
        "amount": 123,
        "scope": None,
        "unit_multiplier": None,
        "vintage_verified": False,
        **changes,
    }


def inputs():
    return Inputs(
        entities=[
            {
                "entity_id": "brand",
                "name": "Brand",
                "prospect": True,
                "shared_symbol": "PRIVATE",
                "handle": "brand",
            }
        ],
        analyses=[{"entity_id": "brand", "analysis_id": "a", "selected": True}],
    )


def snapshot():
    return Snapshot(
        financials=[source_row()],
        metadata={"authenticated": True, "extracted_at": "2026-11-01T00:00:00Z"},
    )


def post(ident, month, likes=None, views=None, **changes):
    return {
        "post_id": ident,
        "profile_id": "p",
        "profile_username": "brand",
        "date_posted": f"2026-{month}-01T00:00:00Z",
        "crawled_at": "2026-10-31T00:00:00Z",
        "like_count": likes,
        "video_view_count": views,
        **changes,
    }


def test_native_revenue_never_aggregates_or_invents_units():
    result = observed_revenue([source_row()], snapshot())
    assert result["observed_revenue_amount"] == 123
    assert result["observed_revenue_period"] == "Shared calendar 2026 Q2"
    assert result["observed_revenue_unit_multiplier"] is None
    assert result["observed_revenue_scope"] is None
    assert "not_score_input" in result["observed_revenue_status"]


def test_segment_source_coverage_without_brand_ticker_excludes_parent_forecast():
    config = inputs()
    config.entities[0].pop("shared_symbol")
    config.analyses[0]["dossier"] = {
        "financial": {
            "entities": {"brand": {"subject": "Coach", "scope": "brand_segment"}}
        }
    }
    segment = source_row(
        source_adapter="issuer_tables_v1",
        financial_subject="Coach",
        scope="brand_segment",
        source_row_id="segment",
        source_relation="denormalized.finance_specific_investor_relations",
    )
    snap = snapshot()
    snap.financials = [segment, segment, source_row(symbol="TPR", kind="forecast")]
    result = FMIResult("brand", "a", {"fmi_status": "unavailable"})
    row = flat_payload([result], config, snap, [])["sheets"][0]["rows"][0]
    assert row["actual_revenue_candidate_count"] == 1
    assert row["forecast_revenue_candidate_count"] == 0
    assert row["revenue_source_status"] == "candidates_retrieved_review_required"
    assert row["observed_revenue_amount"] is None


@pytest.mark.parametrize("same_id", [True, False])
def test_native_revenue_conflicts_remain_unavailable(same_id):
    rows = [
        source_row(),
        source_row(amount=321, source_row_id="native-row" if same_id else "other"),
    ]
    result = observed_revenue(rows, snapshot())
    assert result == {
        "observed_revenue_status": "multiple_latest_candidates_review_required"
    }


def test_revenue_context_rejects_future_and_forecast_observations():
    result = observed_revenue(
        [source_row(date="2026-12-31"), source_row(kind="forecast")], snapshot()
    )
    assert "observed_revenue_amount" not in result


def test_forecast_context_matches_calendar_end_not_fiscal_year_quarter():
    target = {"forecast_target_end": "2026-12-31"}
    rows = [
        source_row(
            source_relation="ai.light_financial_statements_forecast",
            kind="forecast",
            year=2026,
            quarter="Q4",
            reported_date="2026-03-28",
        )
    ]
    result = observed_target_forecast(rows, target)
    assert result["observed_target_forecast_candidate_count"] == 0
    assert "observed_target_forecast_amount" not in result
    rows[0]["reported_date"] = "2026-12-31"
    result = observed_target_forecast(rows, target)
    assert result["observed_target_forecast_amount"] == 123
    assert "unverified" in result["observed_target_forecast_status"]
    rows.append({**rows[0], "source_row_id": "other", "amount": 456})
    result = observed_target_forecast(rows, target)
    assert result["observed_target_forecast_candidate_count"] == 2
    assert "observed_target_forecast_amount" not in result


def test_target_forecast_context_does_not_become_a_score_or_baseline():
    source = snapshot()
    source.financials.append(
        source_row(
            company_code="LIGHT",
            source_relation="ai.light_financial_statements_forecast",
            reported_date="2026-12-31",
            kind="forecast",
            source_row_id="forecast",
        )
    )
    settings = inputs()
    settings.entities[0]["light_code"] = "LIGHT"
    settings.analyses[0]["forecast_target_end"] = "2026-12-31"
    result = FMIResult("brand", "a", values={"fmi_status": "unavailable"})
    row = flat_payload([result], settings, source, [])["sheets"][0]["rows"][0]
    assert row["observed_target_forecast_amount"] == 123
    assert row["raw_fmi"] is row["baseline_revenue"] is row["adjusted_forecast"] is None
    assert row["observed_context_historical_eligible"] is False


def test_source_status_distinguishes_verified_inputs_from_raw_candidates():
    result = FMIResult(
        "brand",
        "a",
        values={
            "fmi_status": "unavailable",
            "financial_coverage_status": "verified_dossier_measurements",
            "social_score": 0,
        },
    )
    row = flat_payload([result], inputs(), snapshot(), [])["sheets"][0]["rows"][0]
    assert row["revenue_source_status"] == "verified_dossier_measurements_retrieved"
    assert row["social_source_status"] == "eligible_social_samples_retrieved"
    assert row["raw_fmi"] is None


def test_flat_contract_preserves_headlines_and_monthly_denominators():
    data = snapshot()
    data.posts = [post("1", "09", 0, 10), post("2", "10", None, 20)]
    result = FMIResult(
        "brand", "a", values={"name": "Brand", "fmi_status": "unavailable"}
    )
    payload = flat_payload([result], inputs(), data, monthly_context(inputs(), data))
    assert payload["kind"] == "flat-delivery"
    assert len(payload["sheets"]) == 1
    sheet = payload["sheets"][0]
    row = sheet["rows"][0]
    assert row["raw_fmi"] is None
    assert row["observed_context_historical_eligible"] is False
    assert row["observed_social_month"] == "2026-10"
    assert row["observed_social_previous_median_likes"] == 0
    assert row["observed_social_median_likes"] is None
    assert row["observed_social_usable_likes"] == 0
    assert row["observed_social_views_change"] == 1
    assert row["actual_revenue_candidate_count"] == 1
    assert set(row) == set(sheet["keys"])
    assert len(sheet["keys"]) == len(set(sheet["keys"]))
    assert all(
        not f["influences_fmi"]
        for f in sheet["fields"]
        if f["field_key"].startswith("observed_")
    )


def test_future_social_capture_filtered_before_deduplication():
    data = snapshot()
    old = post("1", "10", 7)
    data.posts = [old, {**old, "crawled_at": "2026-12-01T00:00:00Z", "like_count": 99}]
    assert monthly_context(inputs(), data)[0]["median_like_count"] == 7


def test_context_uses_calendar_month_not_last_available_month():
    data = snapshot()
    data.posts = [post("1", "08", 7), post("2", "10", 14)]
    result = FMIResult("brand", "a", values={"fmi_status": "unavailable"})
    row = flat_payload([result], inputs(), data, monthly_context(inputs(), data))[
        "sheets"
    ][0]["rows"][0]
    assert row["observed_social_previous_month"] == "2026-09"
    assert row["observed_social_previous_median_likes"] is None
    assert row["observed_social_likes_change"] is None


def test_event_reconciliation_aliases_duplicates_and_unknown_invitation(tmp_path):
    source = tmp_path / "event.csv"
    source.write_text(
        "Brands for FMI Ranking,Category,Invited\n"
        "Michael Kors,Premium,\nMichael Kors,Premium,Y\n"
        "Abercromie & Fitch,Mass Market,\nThe Gap,Mass Market,Y\n"
    )
    entities = [
        {"entity_id": i, "fmi_required": True}
        for i in ("michael-kors", "abercrombie-fitch", "gap-inc")
    ]
    rows = [
        {"brand_id": e["entity_id"], "event_invited": invited}
        for e, invited in zip(entities, [True, None, True], strict=True)
    ]
    audit = event_reconciliation(source, Inputs(entities=entities), rows)
    assert audit["source_rows"] == 4
    assert audit["unique_brands"] == 3
    assert audit["invited_yes"] == 2
    assert audit["missing_inputs"] == audit["missing_delivery"] == []
    assert audit["invitation_mismatch"] == []
    assert set(audit["duplicate_brands"]) == {"michael-kors"}
    audit = event_reconciliation(source, Inputs(entities=entities[:1]), rows[:1])
    assert audit["missing_delivery"] == ["abercrombie-fitch", "gap-inc"]


def test_pipeline_exports_flat_json_and_separate_audit(tmp_path: Path):
    target = tmp_path / "weighted-delivery.xlsx"
    with patch("aily_project.services.fmi.tasks.pipeline.write_workbook") as writer:
        counts = deliver(inputs(), snapshot(), target, Policy())
    rows = json.loads(target.with_suffix(".json").read_text())
    assert isinstance(rows, list)
    assert counts["prospects"] == counts["excluded_prospects"] == 1
    assert len(rows) == counts["exported_prospects"] == 0
    assert writer.call_args.args[0]["sheets"][0]["rows"] == rows
    fields = json.loads((tmp_path / ".work/output-dictionary.json").read_text())
    assert {f["field_key"] for f in fields} == set(
        writer.call_args.args[0]["sheets"][0]["keys"]
    )
    assert {f["sheet_name"] for f in fields} == {"Delivery"}
    audit = json.loads((tmp_path / ".work/delivery-audit.json").read_text())
    assert audit["contract_version"] == "fmi-flat-v3"
    assert "supporting" in audit and "delivery" not in audit
    assert audit["prospect_coverage"][0]["raw_fmi"] is None
    assert audit["prospect_coverage"][0]["observed_revenue_amount"] == 123


def test_delivery_filters_only_unavailable_fmi_keeps_score_without_forecast(tmp_path):
    settings = inputs()
    settings.entities.extend(
        {**settings.entities[0], "entity_id": eid, "name": eid}
        for eid in ("no-forecast", "unavailable", "diagnostic")
    )
    results = [
        FMIResult(
            eid,
            "a",
            values={
                "run_id": "test",
                "name": eid,
                "fmi_status": status,
                "raw_fmi": raw,
                "display_fmi": display,
                "forecast_status": forecast_status,
            },
        )
        for eid, status, raw, display, forecast_status in (
            ("brand", "available", 0, 70, "available"),
            ("no-forecast", "available", 60, 84, "unavailable"),
            ("unavailable", "unavailable", None, None, "unavailable"),
            ("diagnostic", "available", 75, None, "unavailable"),
        )
    ]
    cohort = {"cohort_id": "unchanged", "members": ["brand", "no-forecast"]}
    target = tmp_path / "weighted-delivery.xlsx"
    with (
        patch(
            "aily_project.services.fmi.tasks.pipeline.calculate",
            return_value=(results, cohort),
        ),
        patch("aily_project.services.fmi.tasks.pipeline.write_workbook") as writer,
    ):
        counts = deliver(settings, snapshot(), target, Policy())
    rows = json.loads(target.with_suffix(".json").read_text())
    assert [r["brand_id"] for r in rows] == ["brand", "no-forecast"]
    assert writer.call_args.args[0]["sheets"][0]["rows"] == rows
    assert counts["prospects"] == 4 and counts["exported_prospects"] == 2
    assert counts["excluded_prospects"] == 2
    audit = json.loads((tmp_path / ".work/delivery-audit.json").read_text())
    assert len(audit["prospect_coverage"]) == 4
    assert audit["cohort"] == cohort


def test_dinner_audit_keeps_expected_exclusions_without_blocking_delivery(tmp_path):
    input_path = tmp_path / "inputs/FMI_inputs.json"
    input_path.parent.mkdir()
    save_json(
        {
            "schema_version": "fmi-input-v2",
            "brands": [
                {"id": "brand", "name": "Brand", "required": True, "invited": True},
                {"id": "missing", "name": "Missing", "required": True},
            ],
        },
        input_path,
    )
    raw = input_path.parent / "raw"
    raw.mkdir()
    (raw / "FMI index companies(Sheet1).csv").write_text(
        "Brands for FMI Ranking,Category,Invited\nBrand,Luxe,Y\nMissing,Luxe,\n"
    )
    source = tmp_path / "snapshot.json"
    save_json(
        {
            "financials": [],
            "posts": [],
            "profiles": [],
            "registry": [],
            "overrides": [],
            "metadata": {"authenticated": True, "extracted_at": "2026-11-01T00:00:00Z"},
        },
        source,
    )
    rows = [
        FMIResult(
            eid,
            eid + "-headline",
            values={
                "run_id": "r",
                "name": name,
                "fmi_status": status,
                "raw_fmi": score,
                "display_fmi": display,
                "forecast_status": "unavailable",
                "fmi_required": True,
                "event_invited": invited,
            },
        )
        for eid, name, status, score, display, invited in (
            ("brand", "Brand", "available", 60, 84, True),
            ("missing", "Missing", "unavailable", None, None, None),
        )
    ]
    target, work = tmp_path / "output/weighted-delivery.xlsx", tmp_path / "work"
    with (
        patch(
            "aily_project.services.fmi.tasks.pipeline.calculate",
            return_value=(rows, {"cohort_id": "c"}),
        ),
        patch("aily_project.services.fmi.tasks.pipeline.write_workbook"),
    ):
        delivery_task(input_path, source, target, Policy(), work_dir=work)
    exported = json.loads(target.with_suffix(".json").read_text())
    assert [r["brand_id"] for r in exported] == ["brand"]
    audit = json.loads((work / "dinner-reconciliation.json").read_text())
    assert audit["missing_delivery"] == ["missing"]
    assert audit["missing_inputs"] == audit["missing_calculation_results"] == []
    assert audit["uncovered_fmi_count"] == 1
    assert audit["uncovered_forecast_count"] == 2


def test_explicit_work_directory_keeps_delivery_folder_clean(tmp_path):
    output = tmp_path / "output/weighted-delivery.xlsx"
    work = tmp_path / "internal"
    with patch("aily_project.services.fmi.tasks.pipeline.write_workbook") as writer:
        deliver(inputs(), snapshot(), output, Policy(), work_dir=work)
    assert {p.name for p in output.parent.iterdir()} == {"weighted-delivery.json"}
    assert (work / "output-dictionary.json").is_file()
    assert (work / "coverage.json").is_file()
    assert (work / "brand-runs").is_dir()
    assert writer.call_args.kwargs["work_dir"] == work


def test_audit_and_shareable_directory_cannot_be_the_same(tmp_path):
    with pytest.raises(ValueError, match="separate"):
        deliver(
            inputs(),
            snapshot(),
            tmp_path / "weighted-delivery.xlsx",
            Policy(),
            work_dir=tmp_path,
        )
