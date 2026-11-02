"""File-only JSON inputs, event reconciliation and descriptive-context behavior."""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from aily_project.cli import cli
from aily_project.services.fmi.configuration import (
    document,
    input_policy,
    prepare,
    query_settings,
)
from aily_project.services.fmi.inputs import as_dict, read_inputs
from aily_project.services.fmi.models import Inputs, Snapshot
from aily_project.services.fmi.policy import Policy
from aily_project.services.fmi.run_records import monthly_context, output_dictionary
from aily_project.services.fmi.scoring import legacy_uplift

pytestmark = pytest.mark.unit


def base() -> Inputs:
    return Inputs(
        entities=[
            {
                "entity_id": "brand",
                "name": "Brand",
                "prospect": True,
                "handle": "brand",
            },
            {"entity_id": "peer", "name": "Peer", "prospect": False},
        ],
        analyses=[
            {"analysis_id": "brand-headline", "entity_id": "brand", "selected": True}
        ],
        peers=[
            {
                "analysis_id": "brand-headline",
                "peer_entity_id": "peer",
                "approved": False,
            }
        ],
        financial_review=[
            {
                "analysis_id": "brand-headline",
                "entity_id": "brand",
                "role": "latest",
                "metric": "revenue",
                "source_row_id": "db-id",
                "approved": False,
            }
        ],
    )


def test_json_round_trip_and_policy_override(tmp_path: Path):
    original = base()
    data = document(original, Policy())
    path = tmp_path / "inputs.json"
    data["policy"]["uplift_exponent"] = 4
    path.write_text(json.dumps(data))
    loaded = read_inputs(path)
    # Explicit null settings preserve semantics; source IDs survive unchanged.
    assert loaded.financial_review[0]["source_row_id"] == "db-id"
    assert loaded.peers[0]["approved"] is False
    assert input_policy(path, Policy()).uplift_exponent == 4
    assert query_settings(path)["row_limit"] == 500000
    assert as_dict(original)["entities"] == base().entities


@pytest.mark.parametrize(
    "forbidden", ["amount", "like_count", "available_at", "vintage_verified"]
)
def test_json_cannot_override_source_measurements(tmp_path: Path, forbidden: str):
    data = document(base(), Policy())
    data["brands"][0]["analyses"][0]["financial_selection"][0][forbidden] = 999
    path = tmp_path / "inputs.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="unknown fields"):
        read_inputs(path)


def test_duplicate_event_aliases_preserve_all_mandatory_brands(tmp_path: Path):
    event = tmp_path / "FMI index companies(Sheet1).csv"
    event.write_text(
        "Brands for FMI Ranking,Category,Invited\nMichael Kors,Premium,Y\n"
        "Michael Kors,Premium,Y\nAbercromie & Fitch,Mass Market,\n"
        "Armani,Premium,Y\n"
    )
    original = Inputs(
        entities=[
            {"entity_id": "michael-kors", "name": "Michael Kors", "prospect": True},
            {
                "entity_id": "abercrombie-fitch",
                "name": "Abercrombie & Fitch",
                "prospect": True,
            },
        ]
    )
    with patch(
        "aily_project.services.fmi.configuration.seed_inputs",
        return_value=deepcopy(original),
    ):
        (tmp_path / "brand_peers_dinner prospects.xlsx").touch()
        result = prepare(tmp_path, tmp_path, Policy())
    entities = {b["identity"]["entity_id"]: b["identity"] for b in result["brands"]}
    assert len(entities) == 3
    assert entities["abercrombie-fitch"]["event_invited"] is None
    assert entities["michael-kors"]["event_invited"] is True
    assert entities["armani"]["mapping_approved"] is False
    assert all(e["fmi_required"] for e in entities.values())


@pytest.mark.parametrize(
    "score,rate",
    [(0, 0), (60, 0), (60.001, 0.030002), (70, 0.05), (80, 0.07), (100, 0.11)],
)
def test_legacy_uplift_benchmarks(score: float, rate: float):
    assert legacy_uplift(score, Policy()) == pytest.approx(rate)


def test_monthly_context_missing_vs_zero_and_previous_calendar_month():
    inputs = base()
    snapshot = Snapshot(
        posts=[
            {
                "profile_username": "brand",
                "profile_id": "p",
                "post_id": "1",
                "date_posted": "2025-01-01T00:00:00Z",
                "crawled_at": "2026-01-01T00:00:00Z",
                "like_count": 0,
                "video_view_count": 20,
            },
            {
                "profile_username": "brand",
                "profile_id": "p",
                "post_id": "2",
                "date_posted": "2025-01-02T00:00:00Z",
                "crawled_at": "2026-01-01T00:00:00Z",
                "like_count": None,
                "video_view_count": None,
            },
            {
                "profile_username": "brand",
                "profile_id": "p",
                "post_id": "3",
                "date_posted": "2025-02-01T00:00:00Z",
                "crawled_at": "2026-01-01T00:00:00Z",
                "like_count": 10,
                "video_view_count": 30,
            },
            {
                "profile_username": "brand",
                "profile_id": "p",
                "post_id": "4",
                "date_posted": "2025-04-01T00:00:00Z",
                "crawled_at": "2026-01-01T00:00:00Z",
                "like_count": 10,
            },
        ]
    )
    january, february, april = monthly_context(inputs, snapshot)
    assert january["median_like_count"] == 0
    assert january["usable_like_count"] == 1
    assert february["median_like_count_change"] is None
    assert february["median_video_view_count_change"] == 0.5
    assert april["previous_median_like_count"] is None
    assert all(not r["influences_fmi"] for r in (january, february, april))


def test_monthly_context_timezone_and_conflicting_captures():
    inputs = base()
    post = {
        "profile_username": "brand",
        "profile_id": "p",
        "post_id": "1",
        "date_posted": "2025-03-01T01:00:00+02:00",
        "crawled_at": "2025-03-02T00:00:00Z",
        "like_count": 4,
    }
    assert monthly_context(inputs, Snapshot(posts=[post]))[0]["month"] == "2025-02"
    assert (
        monthly_context(inputs, Snapshot(posts=[post, {**post, "like_count": 5}])) == []
    )
    assert (
        monthly_context(
            inputs, Snapshot(posts=[{**post, "crawled_at": "2025-03-02T00:00:00"}])
        )
        == []
    )


def test_dictionary_covers_each_sheet_column():
    sheets = [
        {
            "name": "Delivery",
            "keys": ["brand_id", "raw_fmi"],
            "labels": ["Brand", "FMI"],
        },
        {"name": "Social monthly context", "keys": ["month"], "labels": ["Month"]},
    ]
    result = output_dictionary(sheets)
    assert {(f["sheet_name"], f["field_key"]) for f in result} == {
        ("Delivery", "brand_id"),
        ("Delivery", "raw_fmi"),
        ("Social monthly context", "month"),
    }


def test_offline_score_never_initializes_cloud(tmp_path: Path):
    path = tmp_path / "inputs.json"
    path.write_text(json.dumps(document(base(), Policy())))
    snap = tmp_path / "snapshot.json"
    snap.write_text(
        json.dumps(
            {
                "metadata": {
                    "authenticated": True,
                    "extracted_at": "2026-10-30T00:00:00Z",
                    "resolved_policy": Policy().model_dump(),
                }
            }
        )
    )
    with patch("aily_project.services.fmi.runner.initialize") as cloud:
        result = CliRunner().invoke(
            cli,
            [
                "fmi",
                "score",
                "--inputs",
                str(path),
                "--snapshot",
                str(snap),
                "--output",
                str(tmp_path / "result.json"),
                "--offline",
            ],
        )
    assert result.exit_code == 0, result.output
    cloud.assert_not_called()
