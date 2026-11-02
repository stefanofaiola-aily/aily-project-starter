"""Explicit published input snapshots remain stable while uplift is renewed."""

from copy import deepcopy

import pytest

from aily_project.services.fmi_dossier.excel import fields_for, finalize, score_rows
from aily_project.services.fmi_dossier.html_delivery import build_payload
from aily_project.services.fmi_dossier.policy import Policy, uplift
from aily_project.services.fmi_dossier.presentation import enrich

pytestmark = pytest.mark.unit


def row(**changes):
    return {
        "brand_id": "fendi",
        "name": "Fendi",
        "include": True,
        "score_method": "reported",
        "reported_fmi": 47,
        "ir_score": 60,
        "social_score": 50,
        "trend_score": 10,
        "dossier_score_basis": "component_percentile_normalized",
        "source_document": "alternative.docx",
        "company_code": "FENDI",
        "published_raw_fmi": 47.3,
        "published_display_fmi": 81.6,
        "published_ir_score": 50.4,
        "published_social_score": 53.6,
        "published_trend_score": 30,
        "published_source_reference": "weighted-delivery-1300.xlsx | Delivery!A10:AI10",
        "published_card_values": {
            "one_core_insight": "Published insight",
            "ir_insight": "FY2025 proxy gap",
            "ir_kpi": 0.0817,
            "social_kpi": 0.0362,
            "trend_kpi": None,
            "source_q4_vs_baseline_2025": -0.02,
        },
        "latest_gap_pp": 2,
        "social_lift_fraction": 0.9,
        "latest_growth": 0.4,
        "baseline_revenue": 100,
        "baseline_kind": "unadjusted_forecast",
        "baseline_approved": True,
        "baseline_source": "forecast.xlsx",
        "baseline_subject": "Fendi",
        "baseline_scope": "brand",
        "baseline_currency": "EUR",
        "baseline_unit_multiplier": 1000000,
        "forecast_target_label": "Q4 2026",
        "forecast_target_start": "2026-10-01",
        "forecast_target_end": "2026-12-31",
        **changes,
    }


def calculate(*inputs):
    return finalize(score_rows(list(inputs), Policy()), Policy())


def test_published_scores_display_cards_and_dossier_alternatives_stay_separate():
    source = row()
    original = deepcopy(source)
    result, cohort = calculate(source)
    r = enrich(result, {})[0]
    assert source == original
    assert [
        r[k]
        for k in ("raw_fmi", "display_fmi", "ir_score", "social_score", "trend_score")
    ] == [47.3, 81.6, 50.4, 53.6, 30]
    assert r["reported_fmi"] == 47
    assert r["dossier_ir_score"] == 60
    assert r["dossier_reported_fmi_difference"] == pytest.approx(0.3)
    assert r["reported_component_difference"] == pytest.approx(-0.02)
    assert r["one_core_insight"] == "Published insight"
    assert r["ir_kpi"] == 0.0817 and r["social_kpi"] == 0.0362
    assert r["trend_kpi"] is None
    assert r["company_code"] == "FENDI"
    assert r["raw_classification"] == "Neutral"
    assert cohort["published_members"] == ["fendi"]
    assert r["uplift_fraction"] == uplift(81.6, Policy())
    assert r["adjusted_forecast"] == 100 * (1 + uplift(81.6, Policy()))


def test_new_cohort_members_never_rescale_published_display_or_uplift():
    alone, _ = calculate(row())
    expanded, _ = calculate(
        row(), row(brand_id="new", published_raw_fmi=None, reported_fmi=100)
    )
    for key in ("raw_fmi", "display_fmi", "uplift_fraction", "adjusted_forecast"):
        assert alone[0][key] == expanded[0][key]
    assert expanded[1]["display_fmi"] == 98
    assert expanded[1]["score_source"] == "dossier"
    assert expanded[0]["display_fmi_basis"] == "published_delivery_preserved"


def test_input_domains_override_reference_without_changing_metrics():
    source = row(email_domains="coach.com; tapestry.com")
    calculated, _ = calculate(source)
    reference = {
        "delivery_snapshots": {
            "fendi": {
                "values": {"email_domains": "tapestry.com"},
                "source_reference": "Frozen snapshot",
            }
        }
    }
    enriched = enrich(calculated, reference)[0]
    assert enriched["email_domains"] == "coach.com; tapestry.com"
    for key in ("raw_fmi", "display_fmi", "uplift_fraction", "adjusted_forecast"):
        assert enriched[key] == calculated[0][key]
    field = next(f.record() for f in fields_for([enriched]) if f.key == "email_domains")
    assert field["source_kind"] == "reviewed_input"


def test_blank_published_history_never_erases_input_or_later_source_history():
    source = row(
        source_social_2024=0.3834,
        source_social_2025=0.0362,
        source_social_2026=-0.4161,
        source_q4_vs_baseline_2024=0,
        source_q4_sales_yoy_2025=0,
        source_snapshot_reference="Reviewed history input",
        published_card_values={
            "source_social_2024": None,
            "source_social_2025": None,
            "source_social_2026": None,
            "source_q4_vs_baseline_2024": None,
            "source_q4_vs_baseline_2025": None,
            "trend_kpi": None,
        },
    )
    result, _ = calculate(source)
    reference = {
        "delivery_snapshots": {
            "fendi": {
                "values": {
                    "source_q4_vs_baseline_2024": 0.2,
                    "source_q4_vs_baseline_2025": 0,
                },
                "source_reference": "Later handover",
            }
        }
    }
    r = enrich(result, reference)[0]
    assert [r[f"source_social_{year}"] for year in (2024, 2025, 2026)] == [
        0.3834,
        0.0362,
        -0.4161,
    ]
    assert r["source_q4_vs_baseline_2024"] == 0
    assert r["source_q4_vs_baseline_2025"] == 0
    assert r["source_snapshot_reference"] == "Reviewed history input"
    assert r["trend_kpi"] is None
    assert [r[k] for k in ("raw_fmi", "display_fmi", "uplift_fraction")] == [
        result[0][k] for k in ("raw_fmi", "display_fmi", "uplift_fraction")
    ]
    payload = build_payload(
        {
            "schema_version": "fmi-dossier-delivery-v2",
            "rows": [r],
            "fields": [f.record() for f in fields_for([r])],
        }
    )["sheets"][0]["rows"][0]
    assert payload["source_social_2026"] == -0.4161
    assert payload["source_q4_vs_baseline_2025"] == 0
    assert payload["source_q4_vs_baseline_2026"] is None


def test_published_history_fills_missing_only_and_preserves_zero():
    result, _ = calculate(
        row(
            source_social_2024=0,
            published_card_values={
                "source_social_2024": 0.5,
                "source_social_2025": 0,
            },
        )
    )
    r = enrich(result, {})[0]
    assert r["source_social_2024"] == 0
    assert r["source_social_2025"] == 0
    assert r.get("source_social_2026") is None


@pytest.mark.parametrize(
    "changes",
    [
        {"published_source_reference": None},
        {"published_display_fmi": None},
        {"published_ir_score": -1},
        {"published_raw_fmi": True},
        {"published_social_score": float("nan")},
        {"published_trend_score": 101},
        {"published_card_values": {"company_code": "PARENT"}},
        {"published_card_values": []},
    ],
)
def test_invalid_or_identity_overwriting_published_snapshot_rejected(changes):
    with pytest.raises(ValueError, match="published"):
        calculate(row(**changes))


def test_zero_published_score_is_not_missing_and_exclusion_still_applies():
    result, _ = calculate(
        row(published_raw_fmi=0), row(brand_id="excluded", include=False)
    )
    assert result[0]["raw_fmi"] == 0
    assert result[1]["display_fmi"] is None


def test_missing_armani_dossier_keeps_forecast_and_reasons_without_duplicate():
    results, _ = calculate(
        row(
            brand_id="armani",
            name="Armani",
            reported_fmi=None,
            published_raw_fmi=None,
            ir_score=None,
            social_score=None,
            trend_score=None,
            limitations=(
                "No FY2024/FY2025 main-account history; FY2023 revenue missing."
            ),
        )
    )
    result = enrich(results, {})
    assert len(result) == 1
    assert result[0]["raw_fmi"] is None and result[0]["adjusted_forecast"] is None
    assert result[0]["baseline_revenue"] == 100
    assert "FY2023" in result[0]["one_core_insight"]


def test_html_copies_published_scores_but_replaces_projection_and_no_db_access():
    results, _ = calculate(row())
    results = enrich(results, {})
    contract = {
        "schema_version": "fmi-dossier-delivery-v2",
        "rows": results,
        "fields": [f.record() for f in fields_for(results)],
    }
    payload = build_payload(contract)
    r = payload["sheets"][0]["rows"][0]
    assert r["raw_fmi"] == 47.3 and r["display_fmi"] == 81.6
    assert r["one_core_insight"] == "Published insight"
    assert r["source_q4_vs_baseline_2025"] is None  # No historical sales YoY supplied.
    assert r["source_q4_vs_baseline_2026"] is None  # No comparable PY forecast.
    assert "published" in r["revenue_methodology"].lower()
    assert "baseline" in r["source_insights_statistics"]
    assert "unavailable" in r["source_insights_descriptive"]
    dictionary = {f.key: f for f in fields_for(results)}
    assert dictionary["published_card_values"].type == "object"
    assert dictionary["published_raw_fmi"].influences_fmi
