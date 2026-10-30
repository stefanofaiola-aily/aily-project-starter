"""Read-only download contracts; fake collaborators, no cloud access."""

import runpy
from pathlib import Path

import pandas as pd
import pytest

FMI = runpy.run_path(str(Path(__file__).parents[1] / "fmi.py"))
pytestmark = pytest.mark.unit


def test_light_download_retains_native_fields_without_inventing_metadata() -> None:
    calls = []
    native = [
        "company_code",
        "reported_date",
        "year",
        "quarter",
        "type_filter_code",
        "type_filter_value",
    ]
    rows = [
        {
            "company_code": "BRBY.L",
            "reported_date": "2026-03-31",
            "year": 2026,
            "quarter": "Q4",
            "type_filter_code": "revenue",
            "type_filter_value": amount,
        }
        for amount in (100, 105)
    ]

    class FakeDB:
        def execute_and_fetch(self, query: str, **kwargs: object) -> list[dict]:
            calls.append((query, kwargs))
            if "current_setting" in query:
                return [{"read_only": "on"}]
            if "information_schema.columns" in query:
                return [{"column_name": col} for col in native]
            return rows

    result = FMI["export_light_revenue"](
        FakeDB(),
        "forecasts",
        {"burberry": "BRBY.L"},
        2023,
        2027,
    )
    assert len(result) == 2  # Different source values are never summed into one row.
    assert result["amount"].tolist() == [100, 105]
    assert result["entity"].eq("burberry").all()
    assert result["classification"].eq("Forecast").all()
    for col in (
        "currency",
        "unit_multiplier",
        "scope",
        "period_start",
        "period_end",
        "published_at",
        "version",
    ):
        assert result[col].isna().all()
    assert all(col in result for col in native)
    assert result["source_row_id"].nunique() == 2
    query, kwargs = calls[-1]
    assert "BRBY.L" not in query
    assert kwargs["bind_params"] == ("BRBY.L", "revenue", 2023, 2027, 10001)
    with pytest.raises(ValueError, match="exceeds row limit"):
        FMI["export_light_revenue"](
            FakeDB(),
            "actuals",
            {"burberry": "BRBY.L"},
            2023,
            2027,
            limit=1,
        )
    with pytest.raises(ValueError, match="Choose actuals or forecasts"):
        FMI["export_light_revenue"](
            FakeDB(),
            "unknown",
            {"burberry": "BRBY.L"},
            2023,
            2027,
        )


def test_light_annotation_can_supply_explicitly_reviewed_fiscal_metadata() -> None:
    raw = pd.DataFrame(
        [
            {
                "entity": "brand",
                "source_row_id": "row1",
                "scope": None,
                "currency": None,
                "unit_multiplier": None,
                "period_start": None,
                "period_end": None,
                "source_locator": "Light row",
            }
        ]
    )
    chosen = pd.DataFrame(
        [
            {
                "entity": "brand",
                "period_role": "latest",
                "source_row_id": "row1",
            }
        ]
    )
    annotations = pd.DataFrame(
        [
            {
                "source_row_id": "row1",
                "scope": "group",
                "currency": "GBP",
                "unit_multiplier": "1",
                "period_start": "2026-01-01",
                "period_end": "2026-03-31",
                "source_locator": "Official fiscal calendar",
            }
        ]
    )
    result = FMI["select_financials"](raw, chosen, annotations)
    assert result.iloc[0]["currency"] == "GBP"
    assert result.iloc[0]["period_start"] == "2026-01-01"
    assert result.iloc[0]["scope"] == "group"
