"""Column-B authority and spelling aliases cannot alter FMI or forecasts."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from aily_project.services.fmi_dossier import categories as service
from aily_project.services.fmi_dossier.presentation import leaderboards, rank_categories

pytestmark = pytest.mark.unit


def read(records, tmp_path, monkeypatch):
    sheet = SimpleNamespace(
        title="Sheet1",
        cell=lambda *args: SimpleNamespace(value="Category"),
        iter_rows=lambda **kwargs: iter(records),
    )
    book = SimpleNamespace(worksheets=[sheet], close=lambda: None)
    monkeypatch.setattr(service, "load_workbook", lambda *a, **kw: book)
    return service.read_categories(tmp_path / "categories.xlsx")


def test_column_b_categories_and_reviewed_aliases(tmp_path, monkeypatch):
    assignments = read(
        [("Hermes", "Luxe"), ("Ralh Lauren", "Premium"), ("The Gap", "Mass Market")],
        tmp_path,
        monkeypatch,
    )
    assert assignments["hermès"]["category"] == "LUXE"
    assert assignments["ralph lauren"]["category"] == "PREMIUM"
    assert assignments["gap inc"]["category"] == "MASS_MARKET"
    assert assignments["hermès"]["source"].endswith("Sheet1!B2")
    assert service.category_identity("Abercromie & Fitch") == (
        service.category_identity("Abercrombie & Fitch")
    )
    assert service.category_identity("Coach") != service.category_identity("Tapestry")


@pytest.mark.parametrize("value", ["RETAILER", "FAST FOLLOWER", "OTHER", "Unknown"])
def test_old_or_unknown_categories_are_rejected(value, tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="Unsupported category"):
        read([("Brand", value)], tmp_path, monkeypatch)


def test_duplicate_alias_and_blank_category_are_explicit(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="Duplicate category"):
        read([("Hermes", "Luxe"), ("Hermès", "Premium")], tmp_path, monkeypatch)
    result = read([("Brand", None), (None, None)], tmp_path, monkeypatch)
    assert result["brand"]["category"] is None


def test_only_assignments_and_ranks_change_not_scores_or_inputs():
    rows = [
        {
            "brand_id": name.lower(),
            "name": name,
            "include": True,
            "has_dossier_data": True,
            "leaderboard_category": "RETAILER",
            "app_category": "OTHER",
            "display_fmi": score,
            "raw_fmi": 47,
            "uplift_fraction": 0.09217,
            "adjusted_forecast": 564.95,
        }
        for name, score in [("Fendi", 83), ("Moncler", 83.9), ("Unlisted", 98)]
    ]
    before = deepcopy(rows)
    assignments = {
        name: {"category": "LUXE", "source": "list.xlsx | Sheet1!B2"}
        for name in ("fendi", "moncler")
    }
    results = service.apply_categories(rows, assignments)
    rank_categories(results)
    assert rows == before
    assert [r["leaderboard_rank"] for r in results] == [2, 1, None]
    assert [r["leaderboard_category"] for r in results] == ["LUXE", "LUXE", None]
    assert results[2]["leaderboard_category_assignment_status"] == (
        "not_in_current_category_list"
    )
    assert set(leaderboards(results)) == {"LUXE", "PREMIUM", "MASS_MARKET"}
    for old, new in zip(before, results, strict=True):
        for key in ("display_fmi", "raw_fmi", "uplift_fraction", "adjusted_forecast"):
            assert new[key] == old[key]


def test_later_list_edit_is_applied_without_stale_fallback():
    rows = [{"name": "Fendi", "leaderboard_category": "LUXE"}]
    assignment = {"fendi": {"category": "PREMIUM", "source": "new.xlsx!B2"}}
    assert service.apply_categories(rows, assignment)[0]["leaderboard_category"] == (
        "PREMIUM"
    )
    assert service.apply_categories(rows, {})[0]["leaderboard_category"] is None
