"""Collection is independent of release gates and never imports report values."""

from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pytest

from aily_project.services.fmi.collection import collection_payload, inventory
from aily_project.services.fmi.handover import prepare_candidates, read_reports
from aily_project.services.fmi.models import Inputs, Snapshot, clean

pytestmark = pytest.mark.unit


def test_inventory_discovers_shared_only_symbol_by_name_without_approving():
    class DB:
        def __init__(self, light):
            self.light = light
            self.calls = []

        def fetch_data_as_df(self, query, *, bind_params=()):
            self.calls.append((query, bind_params))
            if "current_setting" in query:
                return pd.DataFrame(
                    [
                        {
                            "transaction_read_only": "on",
                            "default_transaction_read_only": "on",
                        }
                    ]
                )
            if "information_schema" in query:
                relations = (
                    {
                        "light.light_companies": [
                            "company_code",
                            "company_name",
                            "company_ticker",
                        ]
                    }
                    if self.light
                    else {
                        "normalized.finance_fmp_financial_company_symbols": [
                            "name",
                            "symbol",
                            "crawled_at",
                        ],
                        "normalized.v_finance_financial_statements": [
                            "symbol",
                            "calendar_year",
                        ],
                    }
                )
                return pd.DataFrame(
                    [
                        {
                            "table_schema": r.split(".")[0],
                            "table_name": r.split(".")[1],
                            "column_name": c,
                        }
                        for r, cs in relations.items()
                        for c in cs
                    ]
                )
            if self.light:
                return pd.DataFrame(
                    [
                        {
                            "company_code": "LIGHT",
                            "company_name": "Other",
                            "company_ticker": "TICKER",
                        }
                    ]
                )
            if "financial_company_symbols" in query:
                assert "ILIKE ANY(%s)" in query
                assert "%Brand\\_\\%%" in bind_params[0]
                return pd.DataFrame(
                    [
                        {
                            "name": "Brand_% Inc.",
                            "symbol": "SHARED",
                            "crawled_at": "2026-10-01",
                        }
                    ]
                )
            assert "SHARED" in bind_params
            return pd.DataFrame([{"symbol": "SHARED"}])

    inputs = Inputs(
        entities=[{"entity_id": "brand", "name": "Brand_%", "mapping_approved": False}]
    )
    before = deepcopy(inputs)
    light, shared = DB(True), DB(False)
    result = inventory(light, shared, 2022, 2026, inputs)
    assert inputs == before
    assert result["identity_candidates"][0]["symbol"] == "SHARED"
    assert "SHARED" in result["financial_symbol_search_scope"]
    assert result["financial_symbols"][0]["symbol"] == "SHARED"
    assert "mapping_approved" not in result["identity_candidates"][0]
    assert all(
        q.startswith("SELECT ") and "SELECT *" not in q
        for db in (light, shared)
        for q, _ in db.calls
    )
    assert all(
        "LIMIT %s" in q
        for db in (light, shared)
        for q, _ in db.calls
        if "current_setting" not in q
    )


def test_nat_datetime_is_missing_not_a_date_string():
    assert clean(pd.NaT) is None


def test_report_identity_dates_not_measurements(tmp_path: Path):
    folder = tmp_path / "FMI_delivery" / "02_Brand_reports" / "brand"
    folder.mkdir(parents=True)
    path = folder / "brand_momentum.docx"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/'
            'wordprocessingml/2006/main"><w:body>'
            "<w:p><w:r><w:t>Brand momentum</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>Account @brand. Report revenue 999.</w:t>"
            "</w:r></w:p><w:tbl><w:tr>"
            "<w:tc><w:p><w:r><w:t>Collection</w:t></w:r></w:p></w:tc>"
            "<w:tc><w:p><w:r><w:t>Show date</w:t></w:r></w:p></w:tc>"
            "</w:tr><w:tr>"
            "<w:tc><w:p><w:r><w:t>SS26</w:t></w:r></w:p></w:tc>"
            "<w:tc><w:p><w:r><w:t>10 September 2025</w:t></w:r>"
            "</w:p></w:tc></w:tr></w:tbl></w:body></w:document>",
        )
    report = read_reports(tmp_path)[0]
    assert report["handles"] == ["brand"]
    assert report["shows"][0]["show_date"] == "2025-09-10"
    assert "amount" not in report and "revenue" not in report


def test_collection_proposals_preserve_reviews_and_code_ticker_split():
    inputs = Inputs(
        entities=[
            {"entity_id": "brand", "name": "Brand LLC", "mapping_approved": False},
            {
                "entity_id": "reviewed",
                "name": "Reviewed",
                "mapping_approved": True,
                "light_code": "ORIGINAL",
                "handle": "original",
                "evidence": "user decision",
            },
        ]
    )
    data = {
        "registry": [
            {
                "company_code": "LIGHT",
                "company_label": "Brand",
                "company_ticker": "TICKER",
            },
            {
                "company_code": "NEW",
                "company_label": "Reviewed",
                "company_ticker": "NEW",
            },
        ],
        "accounts": [{"profile_username": "brand", "profile_id": "1"}],
    }
    old = deepcopy(inputs)
    proposed, _ = prepare_candidates(inputs, data, [])
    assert proposed.entities[0]["light_code"] == "LIGHT"
    assert proposed.entities[0]["ticker"] == "TICKER"
    assert proposed.entities[0]["mapping_approved"] is False
    assert proposed.entities[1] == old.entities[1]
    assert inputs == old


def test_group_accounts_not_inferred_from_multi_brand_report():
    inputs = Inputs(entities=[{"entity_id": "group", "name": "Group"}])
    data = {
        "registry": [],
        "accounts": [{"profile_username": "brand1"}, {"profile_username": "brand2"}],
    }
    reports = [
        {
            "report_name": "group",
            "handles": ["brand1", "brand2"],
            "path": "report",
            "shows": [],
            "scope_evidence": [],
        }
    ]
    proposed, audit = prepare_candidates(inputs, data, reports)
    assert not proposed.entities[0].get("handle")
    assert audit[0]["candidate_handles"] == ["brand1", "brand2"]


def test_source_candidates_visible_without_score_approvals():
    inputs = Inputs(
        entities=[
            {
                "entity_id": "brand",
                "name": "Brand",
                "prospect": True,
                "light_code": "CODE",
                "handle": "brand",
                "mapping_approved": False,
            }
        ]
    )
    snapshot = Snapshot(
        financials=[
            {
                "company_code": "CODE",
                "metric": "revenue",
                "kind": "actual",
                "amount": 100,
                "source_relation": "light.actuals",
                "source_row_id": "f",
                "vintage_verified": False,
            }
        ],
        posts=[
            {
                "profile_username": "brand",
                "post_id": str(i),
                "date_posted": "2025-01-01T00:00:00Z",
                "crawled_at": "2026-10-30T00:00:00Z",
                "like_count": likes,
                "source_relation": "normalized.posts",
            }
            for i, likes in enumerate([None, 0, 20])
        ],
        metadata={
            "first_year": 2024,
            "last_year": 2026,
            "extracted_at": "2026-10-30T00:00:00Z",
            "queries": [],
        },
    )
    audit = [
        {
            "entity_id": "brand",
            "report_count": 0,
            "report_paths": [],
            "identity_status": "candidate_found",
        }
    ]
    payload = collection_payload(inputs, snapshot, audit, [])
    row = payload["sheets"][0]["rows"][0]
    assert row["actual_revenue_rows"] == 1
    assert row["usable_likes_posts"] == 2
    assert row["score_release_status"] == "review_required"
    metrics = payload["sheets"][2]["rows"][0]
    assert metrics["median_like_count"] == 10
    assert metrics["usable_like_count"] == 2
    assert metrics["median_comment_count"] is None
    assert "not historical replay" in metrics["measurement_basis"]
    assert payload["sheets"][1]["rows"][0]["amount"] == 100


def test_inventory_discovers_provider_specific_columns_and_checks_read_only():
    class DB:
        def __init__(self, is_light):
            self.is_light = is_light
            self.calls = []

        def fetch_data_as_df(self, query, *, bind_params=()):
            self.calls.append(query)
            if "current_setting" in query:
                return pd.DataFrame(
                    [
                        {
                            "transaction_read_only": "on",
                            "default_transaction_read_only": "on",
                        }
                    ]
                )
            if "information_schema" in query:
                relation = (
                    "light.light_companies"
                    if self.is_light
                    else "denormalized.social_media_bright_data_instagram_posts"
                )
                columns = (
                    ["company_code", "company_label"]
                    if self.is_light
                    else ["user_posted", "user_posted_id", "date_posted"]
                )
                return pd.DataFrame(
                    [
                        {
                            "table_schema": relation.split(".")[0],
                            "table_name": relation.split(".")[1],
                            "column_name": c,
                        }
                        for c in columns
                    ]
                )
            if self.is_light:
                return pd.DataFrame(
                    [{"company_code": "CODE", "company_label": "Brand"}]
                )
            return pd.DataFrame([{"user_posted": "brand", "user_posted_id": "123"}])

    light, shared = DB(True), DB(False)
    result = inventory(light, shared, 2023, 2026)
    assert result["accounts"][0]["profile_username"] == "brand"
    assert result["accounts"][0]["profile_id"] == "123"
    assert all("current_setting" in db.calls[0] for db in (light, shared))
    assert all(
        q.startswith("SELECT ") and "SELECT *" not in q
        for db in (light, shared)
        for q in db.calls
    )


def test_corporate_report_account_precedes_same_name_banner():
    inputs = Inputs(entities=[{"entity_id": "company", "name": "Company"}])
    data = {
        "registry": [],
        "accounts": [
            {"profile_username": "company"},
            {"profile_username": "companyinc"},
        ],
    }
    reports = [
        {
            "report_name": "company",
            "handles": ["company", "companyinc"],
            "preferred_handles": ["companyinc"],
            "path": "report",
            "shows": [],
            "scope_evidence": [],
        }
    ]
    proposed, _ = prepare_candidates(inputs, data, reports)
    assert proposed.entities[0]["handle"] == "companyinc"
    assert not proposed.entities[0].get("mapping_approved")


def test_peer_source_rows_retained_without_multiplying_prospect_coverage():
    inputs = Inputs(
        entities=[
            {
                "entity_id": eid,
                "name": eid,
                "prospect": eid == "brand",
                "light_code": eid.upper(),
            }
            for eid in ("brand", "peer")
        ]
    )
    snapshot = Snapshot(
        financials=[
            {
                "company_code": eid.upper(),
                "metric": "revenue",
                "kind": "actual",
                "amount": 100,
                "source_relation": "light.actuals",
                "source_row_id": eid,
            }
            for eid in ("brand", "peer")
        ],
        metadata={
            "first_year": 2024,
            "last_year": 2026,
            "extracted_at": "2026-10-30T00:00:00Z",
            "queries": [],
        },
    )
    audit = [
        {
            "entity_id": eid,
            "report_count": 0,
            "report_paths": [],
            "identity_status": "candidate_found",
        }
        for eid in ("brand", "peer")
    ]
    payload = collection_payload(inputs, snapshot, audit, [])
    coverage = payload["sheets"][0]["rows"]
    assert len(coverage) == 1
    assert coverage[0]["proxy"] is None
    assert {r["brand_id"] for r in payload["sheets"][1]["rows"]} == {"brand", "peer"}
