"""Weighted-layout order and column provenance without files or databases."""

import pytest

from aily_project.services.fmi_dossier.excel import WEIGHTED_COLUMNS, fields_for
from aily_project.services.fmi_dossier.presentation import enrich

pytestmark = pytest.mark.unit


def test_weighted_first_thirty_eight_columns_and_stable_keys():
    fields = fields_for([{"brand_id": "brand", "name": "Brand"}])
    assert [(f.key, f.label) for f in fields[:38]] == WEIGHTED_COLUMNS
    assert [fields[i].key for i in [0, 2, 4, 6, 8, 11, 18, 25, 26]] == [
        "name",
        "raw_fmi",
        "ir_score",
        "social_score",
        "trend_score",
        "company_code",
        "display_fmi",
        "leaderboard_category",
        "leaderboard_rank",
    ]
    assert fields[38].key == "forecast_target_label"
    assert len({f.key for f in fields}) == len(fields)


def test_source_snapshots_are_frozen_and_never_used_as_new_forecast():
    row = {
        "brand_id": "fendi",
        "name": "Fendi",
        "score_method": "reported",
        "raw_fmi": 47,
        "display_fmi": 83,
        "adjusted_forecast": 564.952465,
        "company_code": "FENDI",
    }
    reference = {
        "delivery_snapshots": {
            "fendi": {
                "source_reference": "weighted-delivery.xlsx | Delivery row 10",
                "values": {
                    "source_q4_vs_baseline_2026": 0.0732,
                    "source_q4_sales_yoy_2026": -0.01308528,
                    "email_domains": "fendi.com; lvmh.com",
                },
            }
        }
    }
    result = enrich([row], reference)[0]
    assert result["source_q4_sales_yoy_2026"] == -0.01308528
    assert result["source_q4_vs_baseline_2026"] == 0.0732
    assert result["adjusted_forecast"] == row["adjusted_forecast"]
    assert result["company_code"] == "FENDI"
    assert "source_q4_sales_yoy_2026" not in row
    fields = {f.key: f for f in fields_for([result])}
    assert fields["source_q4_sales_yoy_2026"].unit == "fraction"
    assert fields["source_q4_sales_yoy_2026"].source_kind == "historical_snapshot"
    assert not fields["source_q4_sales_yoy_2026"].influences_fmi


def test_origins_distinguish_scores_forecasts_and_comparison():
    fields = {
        f.key: f
        for f in fields_for(
            [
                {
                    "brand_id": "brand",
                    "reported_fmi": 47,
                    "source_display_fmi": 81.6,
                    "latest_revenue": 100,
                    "weighted_reference_raw_fmi": 47.3,
                    "weighted_reference_raw_fmi_difference": -0.3,
                }
            ]
        )
    }
    assert "score_source" in fields["raw_fmi"].source_fields
    assert "published_raw_fmi" in fields["raw_fmi"].source_fields
    assert fields["uplift_fraction"].source_fields == ("display_fmi", "policy.uplift_*")
    assert (
        fields["source_legacy_uplift_fraction"].source_fields[0] == "source_display_fmi"
    )
    assert fields["baseline_revenue"].source_kind == "input_excel"
    assert "Light" in fields["company_code"].source_reference
    assert fields["weighted_reference_raw_fmi"].source_kind == "historical_reference"
    assert fields["weighted_reference_raw_fmi_difference"].source_fields == (
        "raw_fmi",
        "weighted_reference_raw_fmi",
    )
    assert all(f.source_reference and f.source_fields for f in fields.values())
