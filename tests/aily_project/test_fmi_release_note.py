"""Release counts are derived, never stale hand-maintained totals."""

import pytest

from aily_project.services.fmi.policy import Policy
from aily_project.services.fmi.release_note import official_run_note

pytestmark = pytest.mark.unit


def test_official_note_preserves_missing_dinner_and_proxy_scope():
    rows = [
        {
            "brand_id": "a",
            "name": "Brand A",
            "fmi_status": "available",
            "adjusted_forecast": 110,
            "parent_name": "Group",
            "financial_subject": "Group",
            "parent_fallback_status": "used_authorized_parent_proxy",
            "latest_period_end": "2026-06-30",
        },
        {
            "brand_id": "b",
            "name": "Brand B",
            "fmi_status": "unavailable",
            "latest_growth": 0.1,
            "earlier_growth": 0.2,
            "used_peer_count": 1,
            "social_status": "unavailable",
            "current_usable_likes": 4,
            "baseline_usable_likes": 2,
            "common_months": 2,
            "missing_reasons": "social:insufficient_posts",
            "score_next_step": "Acquire baseline likes",
        },
    ]
    note = official_run_note(
        {
            "prospect_coverage": rows,
            "source_extracted_at": "2026-11-01T23:00:00Z",
            "run_id": "run",
            "policy": Policy().model_dump(),
        },
        {"brands": [{"brand_id": "a"}, {"brand_id": "b"}]},
        [{"brand_id": "b", "baseline_revenue": None}],
    )
    assert "evaluated all 2 prospects" in note
    assert "Delivered 1 database-derived FMI" in note
    assert "1 dinner brands remain unavailable" in note
    assert "1 dinner references" in note
    assert "scenarios exist for 0 scope-matched" in note
    assert "Brand B | Usable likes posts current/baseline: 4/2" in note
    assert "Recover comparable social history" in note
    assert "Brand A | Group | used_authorized_parent_proxy" in note
    assert "NOT standalone brand" in note


def test_note_without_event_or_dossiers():
    note = official_run_note(
        {
            "prospect_coverage": [],
            "source_extracted_at": "2026-11-01T23:00:00Z",
            "run_id": "run",
            "policy": Policy().model_dump(),
        },
        {},
        [],
    )
    assert "all 0 mandatory dinner brands" in note
    assert "preserve 0 exact supplied report" in note
