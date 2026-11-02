"""Reproducible coverage report without databases or spreadsheet authoring."""

from copy import deepcopy

import pytest
from click.testing import CliRunner

from aily_project.cli import cli
from aily_project.services.fmi.compact_inputs import materialize
from aily_project.services.fmi.data_handoff import (
    actions,
    amount,
    build_handoff,
    query_pack,
    sql_literal,
    text,
    windows,
)
from aily_project.services.fmi.models import FMIResult, Snapshot
from aily_project.services.fmi.policy import Policy
from aily_project.services.fmi.scenario import ACTUAL, FORECAST

pytestmark = pytest.mark.unit


@pytest.fixture
def handoff_case():
    inputs = materialize(
        {
            "mode": "presentation",
            "financial_basis": "latest_available",
            "forecast": {
                "label": "Calendar Q4 2026",
                "start": "2026-10-01",
                "end": "2026-12-31",
            },
            "brands": [
                {
                    "id": "brand",
                    "name": "Brand",
                    "light_code": "BRAND",
                    "instagram": "brand",
                    "profile_id": "p",
                    "required": True,
                    "peers": ["peer", "missing"],
                    "analysis": {
                        "route": "show",
                        "show_date": "2025-09-01",
                        "timezone": "Europe/Paris",
                    },
                }
            ],
            "peer_entities": [
                {"id": "peer", "name": "Peer", "light_code": "PEER"},
                {"id": "missing", "name": "Missing", "shared_symbol": "MISSING"},
            ],
        }
    )
    snapshot = Snapshot(
        registry=[{"company_code": "BRAND"}, {"company_code": "PEER"}],
        metadata={
            "authenticated": True,
            "extracted_at": "2026-11-01T22:00:00Z",
            "first_year": 2022,
            "last_year": 2027,
            "row_limit": 500000,
            "queries": [
                {
                    "source_relation": ACTUAL,
                    "columns": ["company_code", "year"],
                    "query": f"SELECT company_code, year FROM {ACTUAL} "
                    "WHERE company_code IN (%s) AND year BETWEEN %s AND %s LIMIT %s",
                    "scope": ["BRAND", 2022, 2027],
                    "row_count": 3,
                }
            ],
        },
    )
    for code, values in (("BRAND", [100, 110, 132]), ("PEER", [100, 105, 115.5])):
        for year, value in zip((2023, 2024, 2025), values, strict=True):
            snapshot.financials.append(
                {
                    "company_code": code,
                    "year": year,
                    "quarter": "Q4",
                    "reported_date": f"{year}-12-31",
                    "period_label": f"Native {year} Q4",
                    "metric": "revenue",
                    "amount": value,
                    "kind": "actual",
                    "source_relation": ACTUAL,
                    "source_row_id": f"{code}-{year}",
                }
            )
    snapshot.financials.append(
        {
            **snapshot.financials[2],
            "kind": "forecast",
            "amount": 200,
            "year": 2026,
            "reported_date": "2026-12-31",
            "period_label": "Native 2026 Q4",
            "source_relation": FORECAST,
            "source_row_id": "baseline",
        }
    )
    for sample, day, likes in (
        ("current", "2025-09-02", 150),
        ("baseline", "2025-08-20", 100),
    ):
        for n in range(5):
            snapshot.posts.append(
                {
                    "post_id": f"{sample}-{n}",
                    "profile_id": "p",
                    "profile_username": "brand",
                    "date_posted": day + "T12:00:00Z",
                    "crawled_at": "2026-10-30T12:00:00Z",
                    "like_count": likes,
                }
            )
    return inputs, snapshot


def test_handoff_one_missing_peer_uses_one_and_preserves_inputs(handoff_case):
    inputs, snapshot = handoff_case
    before = deepcopy((inputs, snapshot))
    report, data = build_handoff(inputs, snapshot, Policy())
    row = data["results"][0]
    assert row["used_peer_count"] == 1
    assert row["raw_fmi"] == pytest.approx(94)
    assert row["forecast_status"] == "available"
    assert "Used peers (1): Peer" in report
    assert "Missing | excluded" in report
    assert "2025-09-01/2025-09-08" in report
    assert "2025-08-02/2025-08-31; 2025-09-09/2025-10-08" in report
    assert "BRAND-2025" in report
    assert "baseline" in report
    assert "All pulled revenue candidates" in report
    assert "Peer-only identity/source coverage" in report
    assert (inputs, snapshot) == before


def test_no_usable_peers_is_fmi_blocker_not_missing_brand_baseline(handoff_case):
    inputs, snapshot = handoff_case
    snapshot.financials = [
        r for r in snapshot.financials if r["company_code"] != "PEER"
    ]
    report, data = build_handoff(inputs, snapshot, Policy())
    row = data["results"][0]
    assert row["fmi_status"] == "unavailable"
    assert row["baseline_revenue"] == 200
    assert "at least one assigned peer" in report
    assert "available baseline is not the blocker" in report
    assert "peers:no_assigned_peer" in report


def test_no_baseline_keeps_valid_fmi_and_rate(handoff_case):
    inputs, snapshot = handoff_case
    snapshot.financials = [r for r in snapshot.financials if r["kind"] != "forecast"]
    report, data = build_handoff(inputs, snapshot, Policy())
    assert data["results"][0]["fmi_status"] == "available"
    assert data["results"][0]["uplift_fraction"] > 0
    assert "forecast:missing_native_quarter" in report


def test_query_pack_binds_exact_scope_escapes_identifiers_and_splits_connections(
    handoff_case,
):
    _, snapshot = handoff_case
    snapshot.metadata["queries"][0]["scope"][0] = "B'R\\AND; DROP TABLE ignored;"
    packed = query_pack(snapshot)
    assert packed.count("BEGIN TRANSACTION READ ONLY;") == 2
    assert packed.count("ROLLBACK;") == 2
    assert "E'B''R\\\\AND; DROP TABLE ignored;'" in packed
    assert "BETWEEN 2022 AND 2027 LIMIT 500001" in packed
    assert "%s" not in packed
    assert packed.index(ACTUAL) < packed.index("SHARED CONNECTION SECTION")


@pytest.mark.parametrize(
    "bad", ["DELETE FROM t", "SELECT * FROM t; DELETE FROM t", "SELECT * FROM t"]
)
def test_query_pack_rejects_non_read_only_or_multiple_statements(handoff_case, bad):
    _, snapshot = handoff_case
    snapshot.metadata["queries"][0]["query"] = bad
    with pytest.raises(ValueError, match="bounded SELECT"):
        query_pack(snapshot)


def test_missing_and_zero_are_not_conflated():
    assert amount(None) == "missing"
    assert amount(0) == "0"
    assert text("a|b\nc") == "a\\|b c"
    assert sql_literal(None) == "NULL"
    assert sql_literal(False) == "FALSE"
    with pytest.raises(ValueError):
        sql_literal(float("nan"))
    with pytest.raises(ValueError):
        sql_literal([])


def test_windows_fallback_and_explicit_values(handoff_case):
    inputs, _ = handoff_case
    assert windows(
        inputs.analyses[0], {"current_window": "current", "baseline_window": "base"}
    ) == ("current", "base")
    analysis = dict(inputs.analyses[0])
    analysis.pop("route")
    assert windows(analysis, {}) == ("2025-10-01/2025-12-31", "2024-10-01/2024-12-31")


def test_cli_help_never_initializes_cloud():
    result = CliRunner().invoke(cli, ["fmi", "data-handoff", "--help"])
    assert result.exit_code == 0
    assert "--snapshot" in result.output


def test_missing_metadata_and_unassigned_peers_are_not_backfill_requests():
    result = FMIResult(
        "brand",
        "headline",
        {
            "baseline_revenue": 200,
            "prior_year_actual_status": "forecast_prior_year_currency_units"
            "_or_scope_conflict",
        },
        ["peers:no_assigned_peer_with_comparable_three_quarter_series"],
    )
    steps = " ".join(actions(result))
    assert "no peers are assigned" in steps
    assert "actual may already be present" in steps
    assert "Do not backfill duplicate amounts" in steps


def test_registry_candidates_are_hints_not_automatic_peer_substitution(handoff_case):
    inputs, snapshot = handoff_case
    snapshot.metadata["candidate_mappings"] = [
        {
            "entity_id": "missing",
            "company_code": "PEER",
            "company_name": "Known candidate",
            "company_ticker": "P",
        }
    ]
    report, data = build_handoff(inputs, snapshot, Policy())
    assert data["results"][0]["used_peer_count"] == 1
    assert (
        "Known candidate: code PEER, ticker P, retrieved Light revenue rows 3" in report
    )
    assert "not approved" in report
