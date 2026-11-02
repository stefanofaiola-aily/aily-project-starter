"""Dossier inputs and calculation tests, isolated from Word, AWS and databases."""

import json
from copy import deepcopy
from datetime import datetime

import pytest
from click.testing import CliRunner

from aily_project.services.fmi_dossier import excel as service
from aily_project.services.fmi_dossier.policy import Policy

pytestmark = pytest.mark.unit


def row(**changes):
    return {
        "brand_id": "brand",
        "name": "Brand",
        "include": True,
        "has_dossier_data": True,
        "score_method": "reported",
        "reported_fmi": 61.2,
        "ir_score": 34.49,
        "social_score": 100,
        "trend_score": 70,
        "source_document": "report.docx",
        "dossier_score_basis": "original_weighted_method",
        "baseline_revenue": 100,
        "baseline_kind": "unadjusted_forecast",
        "baseline_approved": True,
        "baseline_source": "source.xlsx | N2",
        "baseline_subject": "Brand",
        "baseline_scope": "standalone",
        "baseline_currency": "USD",
        "baseline_unit_multiplier": 1000000,
        "forecast_target_label": "Q4 2026",
        "forecast_target_start": "2026-10-01",
        "forecast_target_end": "2026-12-31",
        "prior_year_actual": 80,
        "prior_year_actual_status": "comparable",
        **changes,
    }


def calculate(*inputs):
    return service.finalize(service.score_rows(list(inputs), Policy()), Policy())


def test_reported_precision_is_preserved_with_separate_arithmetic():
    rows, _ = calculate(row())
    result = rows[0]
    assert result["raw_fmi"] == 61.2
    assert result["weighted_component_fmi"] == pytest.approx(61.245)
    assert result["display_fmi"] == 84
    assert result["legacy_uplift_fraction"] == pytest.approx(0.0324)
    assert result["adjusted_forecast"] > result["baseline_revenue"]
    assert result["historical_eligibility"] == "not_verified_historical_replay"


def test_explicit_component_mode_changes_score_and_missing_propagates():
    rows, _ = calculate(
        row(score_method="weighted_components"),
        row(brand_id="missing", score_method="weighted_components", social_score=None),
    )
    assert rows[0]["raw_fmi"] == pytest.approx(61.245)
    assert rows[1]["raw_fmi"] is None
    assert rows[1]["ir_contribution"] is not None


def test_source_portfolio_can_have_reported_headline_without_fabricated_components():
    rows, _ = calculate(
        row(
            reported_fmi=47.3,
            ir_score=None,
            social_score=None,
            trend_score=None,
            dossier_score_basis="revenue_weighted_core_brand_portfolio",
        )
    )
    assert rows[0]["raw_fmi"] == 47.3
    assert rows[0]["weighted_component_fmi"] is None


def test_percentile_source_is_not_given_absolute_classification():
    rows, _ = calculate(row(dossier_score_basis="component_percentile_normalized"))
    assert rows[0]["raw_classification"] is None


def test_excel_and_csv_peer_types_have_identical_app_contract():
    peers = [{"company": "Peer", "reportedGrowth": 0.05}]
    evidence = [["FY2025", "annual"]]
    excel, _ = calculate(
        row(peer_observations=json.dumps(peers), period_evidence=json.dumps(evidence))
    )
    csv, _ = calculate(row(peer_observations=peers, period_evidence=evidence))
    assert excel == csv
    fields = {f.key: f for f in service.fields_for(excel)}
    assert fields["peer_observations"].type == "array"


def test_normalization_endpoints_exclusions_empty_and_membership():
    rows, cohort = calculate(
        row(reported_fmi=0),
        row(brand_id="high", reported_fmi=100),
        row(brand_id="excluded", reported_fmi=50, include=False),
    )
    assert [r["display_fmi"] for r in rows] == [70, 98, None]
    assert cohort["members"] == ["brand", "high"]
    empty, cohort = calculate(row(reported_fmi=None))
    assert empty[0]["display_fmi"] is None and cohort["minimum"] is None
    rows, _ = calculate(row(reported_fmi=50), row(brand_id="max", reported_fmi=100))
    assert rows[0]["display_fmi"] == 70
    rows, _ = calculate(
        row(reported_fmi=50),
        row(brand_id="max", reported_fmi=100),
        row(brand_id="min", reported_fmi=0),
    )
    assert rows[0]["display_fmi"] == 84


@pytest.mark.parametrize(
    "changes,status",
    [
        ({"baseline_revenue": None}, "missing_dossier_baseline"),
        ({"baseline_revenue": 0}, "invalid_baseline_nonpositive"),
        ({"baseline_kind": "already_adjusted"}, "baseline_already_adjusted_or_unknown"),
        ({"baseline_approved": False}, "baseline_needs_review"),
        ({"baseline_currency": None}, "baseline_missing_scope_unit_or_period"),
    ],
)
def test_bad_baseline_keeps_fmi_and_rates_but_no_adjusted_amount(changes, status):
    rows, _ = calculate(row(**changes))
    assert rows[0]["raw_fmi"] is not None and rows[0]["uplift_fraction"] is not None
    assert rows[0]["adjusted_forecast"] is None
    assert rows[0]["forecast_status"] == status


def test_comparison_forecast_and_context_never_feed_uplift_or_score():
    source = row(source_projected_forecast=200)
    before, _ = calculate(source)
    source.update(
        source_projected_forecast=900,
        current_median_metric=90000,
        source_social_2026=42,
    )
    after, _ = calculate(source)
    assert before[0]["adjusted_forecast"] == after[0]["adjusted_forecast"]
    assert before[0]["raw_fmi"] == after[0]["raw_fmi"]
    after, _ = calculate(row(prior_year_actual_status="unverified"))
    assert after[0]["baseline_forecast_yoy"] is None


def test_export_is_flat_and_json_field_contract_matches_excel_payload(
    tmp_path, monkeypatch
):
    captured = []
    monkeypatch.setattr(
        service,
        "write_workbook",
        lambda payload, *args, **kwargs: captured.append(payload),
    )
    rows, cohort = calculate(
        row(),
        row(
            brand_id="nodata",
            reported_fmi=None,
            ir_score=None,
            social_score=None,
            trend_score=None,
            baseline_revenue=None,
            has_dossier_data=False,
        ),
    )
    result = service.export_delivery(rows, cohort, Policy(), tmp_path)
    assert len(result["rows"]) == 1
    assert len(captured[0]["sheets"]) == 2
    assert captured[0]["sheets"][0]["rows"] == result["rows"]
    assert captured[0]["sheets"][1]["name"] == "Column guide"
    assert [r["key"] for r in captured[0]["sheets"][1]["rows"]] == [
        f["field_key"] for f in result["fields"]
    ]
    fields = {f["field_key"]: f for f in result["fields"]}
    assert fields["uplift_fraction"]["unit"] == "fraction"
    assert (
        fields["latest_gap_pp"]["unit"] == "pp" if "latest_gap_pp" in fields else True
    )
    assert set(fields) == set(result["rows"][0])
    assert fields["fmi_status"]["unit"] == "text"
    assert fields["ir_score"]["unit"] == "score_0_100"
    assert fields["reported_component_difference"]["unit"] == "score_points"


def test_dossier_export_cannot_overwrite_database_or_historical_files(
    tmp_path, monkeypatch
):
    protected = {
        tmp_path / "weighted-delivery.xlsx": b"database workbook",
        tmp_path / "weighted-delivery.json": b"database JSON",
        tmp_path / "dossier-delivery.xlsx": b"historical workbook",
        tmp_path / "dossier-delivery.json": b"historical JSON",
    }
    for path, content in protected.items():
        path.write_bytes(content)

    def write_workbook(payload, path, **kwargs):
        assert path.name == "dossier-calculated-delivery.xlsx"
        path.write_bytes(b"calculated dossier workbook")

    monkeypatch.setattr(service, "write_workbook", write_workbook)
    rows, cohort = calculate(row())
    result = service.export_delivery(rows, cohort, Policy(), tmp_path)
    assert json.loads((tmp_path / "dossier-calculated-delivery.json").read_text()) == (
        result
    )
    assert (tmp_path / "dossier-calculated-delivery.xlsx").read_bytes() == (
        b"calculated dossier workbook"
    )
    assert all(path.read_bytes() == content for path, content in protected.items())


class Sheet:
    def __init__(self, rows):
        self.values = rows


class Book:
    def __init__(self, rows):
        self.rows = rows

    def __getitem__(self, name):
        assert name == "Inputs"
        return Sheet(self.rows)

    def close(self):
        pass


def test_excel_values_are_read_with_types_and_edits_take_effect(monkeypatch, tmp_path):
    source = row(show_date=datetime(2026, 2, 23))
    keys = list(source)
    records = [keys, list(source.values())]
    monkeypatch.setattr(service, "load_workbook", lambda *args, **kwargs: Book(records))
    loaded = service.read_excel(tmp_path / "input.xlsx")
    assert loaded[0]["show_date"] == "2026-02-23"
    source["reported_fmi"] = 80
    records[1] = list(source.values())
    assert (
        service.score_rows(service.read_excel(tmp_path / "input.xlsx"), Policy())[0][
            "raw_fmi"
        ]
        == 80
    )
    assert loaded[0]["reported_fmi"] == 61.2


@pytest.mark.parametrize(
    "change", [{"reported_fmi": "=1+1"}, {"reported_fmi": "bad"}, {"include": "maybe"}]
)
def test_excel_invalid_values_rejected(change, monkeypatch, tmp_path):
    source = row(**change)
    records = [list(source), list(source.values())]
    monkeypatch.setattr(service, "load_workbook", lambda *args, **kwargs: Book(records))
    with pytest.raises(ValueError):
        service.read_excel(tmp_path / "input.xlsx")


def test_duplicate_ids_rejected(monkeypatch, tmp_path):
    source = row()
    records = [list(source), list(source.values()), deepcopy(list(source.values()))]
    monkeypatch.setattr(service, "load_workbook", lambda *args, **kwargs: Book(records))
    with pytest.raises(ValueError, match="duplicate"):
        service.read_excel(tmp_path / "input.xlsx")


def test_dossier_cli_recalculates_edits_without_cloud_or_source_writes(
    monkeypatch, tmp_path
):
    from aily_project.services.fmi_dossier.runner import fmi_dossier

    source = row(fmi_required=True, event_invited=True)
    for key in [
        "collection",
        "show_date",
        "financial_period_label",
        "baseline_window",
        "current_window",
        "used_peer_names",
        "latest_growth",
        "latest_peer_median_growth",
        "latest_gap_pp",
        "trend_change_pp",
        "social_lift_fraction",
        "source_projected_forecast",
        "limitations",
    ]:
        source[key] = None
    keys = list(source)
    records = [keys, list(source.values())]
    monkeypatch.setattr(service, "load_workbook", lambda *a, **kw: Book(records))
    monkeypatch.setattr(service, "write_workbook", lambda *a, **kw: None)

    def no_cloud(*args, **kwargs):
        raise AssertionError("Offline dossier CLI must not initialize cloud settings")

    monkeypatch.setattr("aily_py_commons.aily_settings.AilySettings", no_cloud)
    output = tmp_path / "output"
    output.mkdir()
    reference = output / "dossier-delivery.json"
    reference.write_text("original reference")
    protected = {
        output / "weighted-delivery.json": b"automated delivery",
        output / "weighted-delivery.xlsx": b"automated workbook",
        output / "dossier-delivery.xlsx": b"original workbook",
        tmp_path / "input.xlsx": b"one-time source workbook",
    }
    for path, content in protected.items():
        path.write_bytes(content)
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text("version: test\n")

    def run():
        result = CliRunner().invoke(
            fmi_dossier,
            [
                "--inputs",
                str(tmp_path / "input.xlsx"),
                "--policy",
                str(policy_path),
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        return json.loads((output / "dossier-calculated-delivery.json").read_text())[
            "rows"
        ]

    assert run()[0]["raw_fmi"] == 61.2
    source["reported_fmi"] = 80
    records[1] = list(source.values())
    assert run()[0]["raw_fmi"] == 80
    source.update(reported_fmi=None, ir_score=None, social_score=None, trend_score=None)
    records[1] = list(source.values())
    assert run()[0]["raw_fmi"] is None
    assert reference.read_text() == "original reference"
    assert not (tmp_path / "automated-output").exists()
    assert all(path.read_bytes() == content for path, content in protected.items())
