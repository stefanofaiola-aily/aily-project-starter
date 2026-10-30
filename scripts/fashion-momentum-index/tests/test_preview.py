"""Preparation guards for real-download previews; no cloud access."""

import runpy
from pathlib import Path

import pandas as pd
import pytest

FMI = runpy.run_path(str(Path(__file__).parents[1] / "fmi.py"))
pytestmark = pytest.mark.unit


def preview_input() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.DataFrame(
        [
            {
                "entity": "brand",
                "year": 2025,
                "quarter": "Q2",
                "classification": "Actual",
                "metric": "revenue",
                "amount": 100,
                "reported_date": "2024-09-28",
                "source_row_id": "row1",
                "currency": None,
                "unit_multiplier": None,
                "scope": None,
            }
        ]
    )
    choices = pd.DataFrame(
        [
            {
                "entity": "brand",
                "year": 2025,
                "quarter": "Q2",
                "classification": "Actual",
                "period_role": "latest",
            }
        ]
    )
    return raw, choices


def test_preview_selects_native_fiscal_period_without_inventing_metadata() -> None:
    raw, choices = preview_input()
    result = FMI["preview_periods"](raw, choices, "2026-10-28T23:59:59Z")
    assert result["source_row_id"].tolist() == ["row1"]
    assert result["amount"].tolist() == [100]
    assert result[["currency", "scope", "unit_multiplier"]].isna().all().all()


@pytest.mark.parametrize("failure", ["missing", "duplicate", "zero", "future", "nan"])
def test_preview_refuses_invalid_periods(failure: str) -> None:
    raw, choices = preview_input()
    if failure == "missing":
        choices["year"] = 2027
    elif failure == "duplicate":
        raw = pd.concat([raw, raw], ignore_index=True)
    elif failure == "zero":
        raw["amount"] = 0
    elif failure == "nan":
        raw["amount"] = float("nan")
    else:
        raw["reported_date"] = "2027-09-28"
    with pytest.raises(ValueError):
        FMI["preview_periods"](raw, choices, "2026-10-28T23:59:59Z")


def test_caption_preview_preserves_manual_review_and_unknowns() -> None:
    posts = pd.DataFrame(
        [
            {"handle": "brand", "post_key": str(i), "description": caption}
            for i, caption in enumerate(
                [
                    "Guest at Summer 2025",
                    "Winter 2024",
                    "New bag",
                    "Summer 2025 Winter 2024",
                ]
            )
        ]
    )
    reviews = pd.DataFrame(
        [{"handle": "brand", "post_key": "0", "collection_related": "false"}]
    )
    original = reviews.copy(deep=True)
    result = FMI["preview_collection_labels"](
        posts, reviews, "Summer 2025", "Winter 2024"
    )
    assert result.loc[0, "collection_related"] == False  # noqa: E712
    assert result.loc[0, "label_source"] == "Existing user review"
    assert result.loc[1, "collection_related"] == False  # noqa: E712
    assert result.loc[2:, "collection_related"].isna().all()
    pd.testing.assert_frame_equal(reviews, original)


def test_social_preview_does_not_change_strict_review_default() -> None:
    _, posts, labels, analysis = FMI["demo_inputs"]()
    analysis["coverage_reviewed"] = False
    with pytest.raises(ValueError, match="Review social coverage"):
        FMI["social_component"](posts, labels, analysis)
    result = FMI["social_component"](posts, labels, analysis, require_review=False)
    assert result["social_score"] == pytest.approx(80)
    assert analysis["coverage_reviewed"] is False
