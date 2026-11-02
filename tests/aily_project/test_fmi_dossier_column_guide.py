"""Column documentation stays aligned without changing delivery calculations."""

from copy import deepcopy

import pytest

from aily_project.services.fmi_dossier.column_guide import (
    build_column_guide,
    column_letter,
)
from aily_project.services.fmi_dossier.excel import fields_for

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("index", "expected"),
    [(1, "A"), (26, "Z"), (27, "AA"), (38, "AL"), (49, "AW"), (247, "IM")],
)
def test_actual_column_letters(index, expected):
    assert column_letter(index) == expected


def test_complete_ordered_dictionary_preserves_fields_and_input():
    row = {"brand_id": "fendi", "name": "Fendi", "raw_fmi": 47}
    original = deepcopy(row)
    fields = fields_for([row])
    before = [field.record() for field in fields]
    guide = build_column_guide(fields)
    assert [entry["key"] for entry in guide["rows"]] == [f.key for f in fields]
    assert len({entry["column"] for entry in guide["rows"]}) == len(fields)
    for index, entry in enumerate(guide["rows"], 1):
        assert entry["column"] == column_letter(index)
        assert set(entry) == set(guide["keys"])
        assert all(entry[k] for k in guide["keys"])
    assert len(guide["labels"]) == len(guide["keys"])
    assert before == [field.record() for field in fields]
    assert row == original


def test_new_forecast_locator_and_denominators_are_unambiguous():
    guide = build_column_guide(fields_for([{"brand_id": "fendi"}]))
    entries = {entry["key"]: entry for entry in guide["rows"]}
    new = entries["adjusted_forecast_vs_py_forecast_yoy"]
    assert new["column"] == "AW"
    assert new["use"] == "Recommended delivery"
    assert "adjusted_forecast (AT)" in new["inputs"]
    assert "prior_year_forecast (AU)" in new["inputs"]
    assert "PY FORECAST" in new["meaning"]
    assert entries["baseline_forecast_vs_py_forecast_yoy"]["column"] == "AV"
    assert entries["fmi_increment_vs_py_forecast_pp"]["column"] == "AX"
    assert entries["source_q4_sales_yoy_2026"]["column"] == "AL"
    assert entries["source_q4_sales_yoy_2026"]["use"] == "Historical / audit only"
    assert entries["source_q4_vs_baseline_2026"]["use"] == "Historical / audit only"
    assert entries["source_legacy_uplift_fraction"]["use"] == "Legacy comparison only"
    assert entries["baseline_is_parent_proxy"]["use"] == "Delivery qualification"
    assert guide["period_column"] == "AM"
    assert {entry["key"] for entry in guide["locators"]} == {
        "adjusted_forecast_vs_py_forecast_yoy",
        "baseline_forecast_vs_py_forecast_yoy",
        "fmi_increment_vs_py_forecast_pp",
        "uplift_fraction",
        "adjusted_forecast",
        "source_q4_sales_yoy_2026",
    }


def test_empty_guide_has_stable_table_headers():
    guide = build_column_guide([])
    assert guide["rows"] == guide["locators"] == []
    assert guide["period_column"] is None
    assert len(guide["keys"]) == len(guide["labels"]) == 10
