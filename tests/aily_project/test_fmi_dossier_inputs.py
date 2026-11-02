"""Dossiers seed parameters; database observations remain the measurements."""

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from aily_project.services.fmi.compact_inputs import materialize
from aily_project.services.fmi.dossier_inputs import align_dossiers, validate_method
from aily_project.services.fmi.dossier_selection import (
    annual_from_quarters,
    series,
    trend,
)
from aily_project.services.fmi.models import Snapshot
from aily_project.services.fmi.policy import Policy
from aily_project.services.fmi.scenario import ACTUAL, FORECAST
from aily_project.services.fmi.scoring import calculate

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def dossier_case():
    periods = {
        role: {"start": f"{year}-04-01", "end": f"{year}-06-30", "type": "quarter"}
        for role, year in zip(
            ("oldest", "earlier", "latest"), (2023, 2024, 2025), strict=True
        )
    }
    method = {
        "source": "handover/verified.docx",
        "financial": {
            "aggregation": "single_reported_observation",
            "entities": {
                eid: {
                    "subject": eid,
                    "scope": "consolidated",
                    "metric": "revenue",
                    "periods": deepcopy(periods),
                }
                for eid in ("brand", "peer")
            },
        },
        "social": {
            "platform": "instagram",
            "metric": "likes",
            "baseline_days": 15,
            "current_days": 7,
            "caption_pattern": "collection2026",
            "min_posts": 5,
        },
        "trend": {"basis": "peer_gap", "rule": "legacy", "comparison": "same_season"},
        "score_basis": "original",
    }
    data = {
        "mode": "dossier",
        "financial_basis": "dossier",
        "forecast": {"label": "Q4 2026", "start": "2026-10-01", "end": "2026-12-31"},
        "brands": [
            {
                "id": "brand",
                "name": "Brand",
                "light_code": "B",
                "ticker": "BT",
                "instagram": "brand",
                "profile_id": "p",
                "peers": ["peer", "missing"],
                "analysis": {
                    "route": "show",
                    "show_date": "2025-09-01",
                    "timezone": "Europe/Paris",
                    "dossier": method,
                },
            }
        ],
        "peer_entities": [
            {"id": "peer", "name": "Peer", "light_code": "P"},
            {"id": "missing", "name": "Missing"},
        ],
    }
    snapshot = Snapshot(
        registry=[{"company_code": "B", "company_ticker": "BT"}, {"company_code": "P"}],
        metadata={"authenticated": True, "extracted_at": "2026-11-01T12:00:00Z"},
    )
    for code, values in (("B", [100, 110, 132]), ("P", [100, 105, 115.5])):
        for year, amount in zip((2023, 2024, 2025), values, strict=True):
            snapshot.financials.append(
                {
                    "company_code": code,
                    "year": year,
                    "quarter": "Q2",
                    "reported_date": f"{year}-06-30",
                    "metric": "revenue",
                    "kind": "actual",
                    "amount": amount,
                    "currency": "USD",
                    "unit_multiplier": 1,
                    "scope": "consolidated",
                    "period_start": f"{year}-04-01",
                    "period_end": f"{year}-06-30",
                    "period_type": "quarter",
                    "period_label": f"FY{year} Q2",
                    "source_relation": ACTUAL,
                    "source_row_id": f"{code}-{year}",
                    "source_classification": "reported",
                }
            )
    snapshot.financials.append(
        {
            **snapshot.financials[2],
            "source_relation": FORECAST,
            "source_row_id": "baseline",
            "kind": "forecast",
            "reported_date": "2026-12-31",
            "period_start": "2026-10-01",
            "period_end": "2026-12-31",
            "year": 2026,
            "quarter": "Q4",
            "amount": 200,
            "period_label": "FY2026 Q4",
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
                    "crawled_at": "2026-10-28T12:00:00Z",
                    "caption": "collection2026",
                    "like_count": likes,
                    "comment_count": 10 if sample == "current" else 5,
                }
            )
    return data, snapshot


def test_dossier_periods_are_independent_of_forecast_and_latest_actual(dossier_case):
    data, snapshot = dossier_case
    snapshot.financials.append(
        {
            **snapshot.financials[2],
            "amount": 9999,
            "source_row_id": "newer",
            "reported_date": "2026-06-30",
            "period_start": "2026-04-01",
            "period_end": "2026-06-30",
        }
    )
    inputs = materialize(data)
    result = calculate(inputs, snapshot, Policy(), "dossier")[0][0]
    v = result.values
    assert v["latest_revenue"] == 132
    assert v["latest_period_end"].isoformat() == "2025-06-30"
    assert v["raw_fmi"] == pytest.approx(94)
    assert v["used_peer_count"] == 1
    assert v["baseline_revenue"] == 200
    assert v["calculation_mode"] == "dossier"
    assert "simulation" not in v["release_status"]
    assert inputs.analyses[0]["baseline_start"] == "2025-08-17"
    data["forecast"].update(label="Q1 2027", start="2027-01-01", end="2027-03-31")
    assert (
        calculate(materialize(data), snapshot, Policy(), "other")[0][0].values[
            "raw_fmi"
        ]
        == v["raw_fmi"]
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("scope", "retail_dtc"),
        ("source_classification", "interpolated"),
        ("currency", None),
        ("unit_multiplier", None),
    ],
)
def test_wrong_scope_or_unverified_source_never_becomes_revenue(
    dossier_case, field, value
):
    data, snapshot = dossier_case
    snapshot.financials[2][field] = value
    result = calculate(materialize(data), snapshot, Policy(), "bad")[0][0]
    assert result.values.get("raw_fmi") is None
    assert result.values.get("latest_revenue") is None
    assert any("missing_verified" in reason for reason in result.gaps)


def test_dossier_comments_not_likes_and_review_wins(dossier_case):
    data, snapshot = dossier_case
    data["brands"][0]["analysis"]["dossier"]["social"]["metric"] = "comments"
    snapshot.posts[0]["like_count"] = None
    result = calculate(materialize(data), snapshot, Policy(), "comments")[0][0]
    assert result.values["social_score"] == 100
    assert result.values["social_scoring_metric"] == "comments"
    inputs = materialize(data)
    inputs.post_review = [
        {
            "analysis_id": "brand-headline",
            "post_key": "p:current-0",
            "reviewed": True,
            "relevant": False,
            "evidence": "Not collection content",
        }
    ]
    result = calculate(inputs, snapshot, Policy(), "review")[0][0]
    assert result.values.get("social_score") is None
    assert (
        next(p for p in result.social_posts if p["post_id"] == "current-0")[
            "inclusion_reason"
        ]
        == "not_collection_post"
    )


def test_company_growth_trend_is_not_peer_gap_trend(dossier_case):
    data, snapshot = dossier_case
    snapshot.financials[5]["amount"] = 136.5  # Peer accelerates much faster.
    peer_result = calculate(materialize(data), snapshot, Policy(), "peer")[0][0]
    data["brands"][0]["analysis"]["dossier"]["trend"]["basis"] = "company_growth"
    company_result = calculate(materialize(data), snapshot, Policy(), "company")[0][0]
    assert peer_result.values["trend_score"] == 30
    assert company_result.values["trend_score"] == 70
    assert company_result.values["trend_change_pp"] == pytest.approx(10)
    assert trend(0, 3, {"basis": "peer_gap", "rule": "legacy"}, Policy())[0] == 70


def test_missing_regex_never_becomes_all_show_posts(dossier_case):
    data, snapshot = dossier_case
    data["brands"][0]["analysis"]["dossier"]["social"].pop("caption_pattern")
    assert (
        calculate(materialize(data), snapshot, Policy(), "relevance")[0][0].values.get(
            "social_score"
        )
        is None
    )


def test_incompatible_baseline_leaves_valid_fmi(dossier_case):
    data, snapshot = dossier_case
    snapshot.financials[-1]["scope"] = "retail_dtc"
    result = calculate(materialize(data), snapshot, Policy(), "baseline")[0][0]
    assert result.values["raw_fmi"] == pytest.approx(94)
    assert result.values["uplift_fraction"] > 0
    assert result.values.get("adjusted_forecast") is None
    assert "scope" in result.values["forecast_missing_reason"]


def test_assumed_trend_is_labelled_even_when_revenue_is_missing(dossier_case):
    data, snapshot = dossier_case
    data["brands"][0]["analysis"]["dossier"]["trend"].update(
        basis="assumed", assumed_score=50
    )
    snapshot.financials = []
    result = calculate(materialize(data), snapshot, Policy(), "assumed")[0][0]
    assert result.values["trend_score"] == 50
    assert result.values["trend_label"] == "dossier_assumed_not_measured"
    assert result.values.get("raw_fmi") is None


def test_post_extraction_financial_observation_cannot_enter_score(dossier_case):
    data, snapshot = dossier_case
    snapshot.financials[2]["available_at"] = "2026-12-01T12:00:00Z"
    result = calculate(materialize(data), snapshot, Policy(), "late")[0][0]
    assert result.values.get("latest_revenue") is None
    assert result.values.get("raw_fmi") is None


def test_context_scope_is_verified_and_does_not_change_fmi(dossier_case):
    data, snapshot = dossier_case
    snapshot.financials.append(
        {
            **snapshot.financials[2],
            "metric": "ebitda",
            "amount": 12,
            "scope": None,
            "source_row_id": "context",
        }
    )
    result = calculate(materialize(data), snapshot, Policy(), "context")[0][0]
    assert result.values["raw_fmi"] == pytest.approx(94)
    assert result.values.get("latest_ebitda") is None


def test_published_growth_is_not_replaced_with_nominal_revenue(dossier_case):
    data, snapshot = dossier_case
    data["brands"][0]["analysis"]["dossier"]["financial"]["growth_basis"] = (
        "published_comparable_growth"
    )
    result = calculate(materialize(data), snapshot, Policy(), "comparable")[0][0]
    assert result.values.get("raw_fmi") is None
    assert any("not_nominal_revenue" in reason for reason in result.gaps)


def test_weighted_headline_is_separate_from_unavailable_historical_percentile(
    dossier_case,
):
    data, snapshot = dossier_case
    data["brands"][0]["analysis"]["dossier"]["score_basis"] = "percentile"
    original = calculate(materialize(data), snapshot, Policy(), "reference")[0][0]
    assert original.values.get("raw_fmi") is None
    assert any("reference_cohort" in reason for reason in original.gaps)
    data["headline_method"] = "weighted_components"
    result = calculate(materialize(data), snapshot, Policy(), "weighted")[0][0]
    assert result.values["raw_fmi"] == pytest.approx(94)
    assert result.values["dossier_score_basis"] == "percentile"
    assert result.values["headline_method"] == "weighted_components"
    assert (
        result.values["dossier_headline_replication_status"]
        == "original_reference_cohort_unavailable"
    )
    assert not any("reference_cohort" in reason for reason in result.gaps)
    snapshot.posts.clear()
    missing = calculate(materialize(data), snapshot, Policy(), "missing")[0][0]
    assert missing.values.get("raw_fmi") is None


def test_unknown_headline_method_is_not_silently_accepted(dossier_case):
    data, _ = dossier_case
    data["headline_method"] = "restore_old_scores"
    with pytest.raises(ValueError, match="Headline method"):
        materialize(data)


@pytest.mark.parametrize(
    "change", [{"platform": "tiktok"}, {"aggregation": "median_member_lifts"}]
)
def test_unsupported_method_does_not_substitute_instagram_group_handle(
    dossier_case, change
):
    data, snapshot = dossier_case
    data["brands"][0]["analysis"]["dossier"]["social"].update(change)
    result = calculate(materialize(data), snapshot, Policy(), "platform")[0][0]
    assert result.values.get("social_score") is None
    assert result.values.get("raw_fmi") is None


def test_native_fiscal_label_does_not_match_shared_calendar_label(dossier_case):
    data, snapshot = dossier_case
    inputs = materialize(data)
    requested = inputs.analyses[0]["dossier"]["financial"]["entities"]["brand"][
        "periods"
    ]["latest"]
    requested.update(label="FY2025", alignment="native_fiscal_year", type="annual")
    requested.pop("start")
    requested.pop("end")
    snapshot.financials[2].update(
        symbol="BT",
        source_relation="normalized.finance_fmp_financial_statements",
        period_label="FY2025",
        period_type="annual",
        period_start="2025-01-01",
        period_end="2025-12-31",
    )
    selected, reasons = series(inputs, inputs.entities[0], snapshot, inputs.analyses[0])
    assert not any(p["role"] == "latest" for p in selected)
    assert any("missing_verified" in r for r in reasons)


def test_explicit_source_subject_is_used_without_automatic_parent_fallback(
    dossier_case,
):
    data, snapshot = dossier_case
    brand = data["brands"][0]
    brand["parent"] = {
        "name": "Unselected parent",
        "light_code": "P",
        "authorized": True,
        "evidence": "ownership",
        "prefer": True,
    }
    original = calculate(materialize(data), snapshot, Policy(), "brand")[0][0]
    assert original.values["light_code"] == "B"
    data["peer_entities"].append(
        {
            "id": "financial-parent",
            "name": "Verified parent",
            "light_code": "B",
            "ticker": "BT",
        }
    )
    spec = brand["analysis"]["dossier"]["financial"]["entities"]["brand"]
    spec.update(source_entity_id="financial-parent", subject="Verified parent")
    brand["light_code"] = "PRIVATE"
    result = calculate(materialize(data), snapshot, Policy(), "parent")[0][0]
    assert result.values["raw_fmi"] == pytest.approx(94)
    assert result.values["light_code"] == "B"
    assert result.values["financial_subject"] == "Verified parent"
    assert "NOT standalone" in result.values["proxy_label"]
    assert result.values["baseline_revenue"] == 200


def test_portfolio_uses_member_lifts_not_pooled_likes(dossier_case):
    data, snapshot = dossier_case
    social = data["brands"][0]["analysis"]["dossier"]["social"]
    social.update(
        aggregation="median_member_lifts",
        min_members=2,
        members=[
            {
                "name": "Small",
                "handle": "brand",
                "route": "show",
                "show_date": "2025-09-01",
                "timezone": "Europe/Paris",
            },
            {
                "name": "Large",
                "handle": "large",
                "route": "show",
                "show_date": "2025-09-01",
                "timezone": "Europe/Paris",
            },
        ],
    )
    snapshot.posts.extend(
        {
            **p,
            "profile_username": "large",
            "profile_id": "large-id",
            "like_count": 10000,
            "post_id": "large-" + p["post_id"],
        }
        for p in list(snapshot.posts)
    )
    result = calculate(materialize(data), snapshot, Policy(), "portfolio")[0][0]
    assert result.values["likes_lift"] == pytest.approx(0.25)
    assert result.values["social_score"] == 75
    assert result.values["social_used_members"] == "Small; Large"
    assert result.values.get("current_median_likes") is None


def test_annual_aggregation_requires_gapless_verified_quarters(dossier_case):
    from datetime import date

    _, snapshot = dossier_case
    periods = [
        ("2025-01-01", "2025-03-31"),
        ("2025-04-01", "2025-06-30"),
        ("2025-07-01", "2025-09-30"),
        ("2025-10-01", "2025-12-31"),
    ]
    rows = [
        {
            **snapshot.financials[0],
            "period_start": date.fromisoformat(s),
            "period_end": date.fromisoformat(e),
            "source_row_id": str(n),
            "amount": 100 + n,
        }
        for n, (s, e) in enumerate(periods)
    ]
    result = annual_from_quarters(rows, date(2025, 1, 1), date(2025, 12, 31))
    assert result is not None and result["amount"] == 406
    assert len(result["underlying_candidates"]) == 4
    rows[2]["period_start"] = date(2025, 7, 2)
    assert annual_from_quarters(rows, date(2025, 1, 1), date(2025, 12, 31)) is None


def test_capture_cutoff_is_applied_before_dossier_deduplication(dossier_case):
    data, snapshot = dossier_case
    data["brands"][0]["analysis"]["dossier"]["social"]["capture_cutoff"] = (
        "2026-10-28T23:59:59Z"
    )
    snapshot.posts.extend(
        {**p, "like_count": 9999, "crawled_at": "2026-10-29T12:00:00Z"}
        for p in list(snapshot.posts)
        if p["post_id"].startswith("current")
    )
    result = calculate(materialize(data), snapshot, Policy(), "cutoff")[0][0]
    assert result.values["current_median_likes"] == 150


def test_measurements_and_invalid_methods_are_not_editable_overrides(dossier_case):
    data, _ = dossier_case
    method = data["brands"][0]["analysis"]["dossier"]
    method["financial"]["entities"]["brand"]["amount"] = 100
    with pytest.raises(ValueError, match="measurement"):
        validate_method(method, {"brand", "peer"})
    with pytest.raises(ValueError, match="Dossier mode"):
        materialize({**data, "financial_basis": "latest_available"})


def test_existing_edits_and_reviews_survive_one_time_alignment(dossier_case, tmp_path):
    data, _ = dossier_case
    data["brands"][0]["review"] = {"identity": {"evidence": "preserve me"}}
    before = deepcopy(data)
    updated, audit = align_dossiers(data, tmp_path)
    assert updated == before
    assert audit[0]["status"] == "existing_dossier_parameters_preserved"


def test_actual_handover_keeps_all_prospects_and_selects_scored_moncler_cycle(
    tmp_path,
):
    base = ROOT / "scripts/fashion-momentum-index"
    data = json.loads((base / "inputs/FMI_inputs.json").read_text())
    # Re-seed without requiring the optional external roadmap repository.
    for brand in data["brands"]:
        brand.get("analysis", {}).pop("dossier", None)
    # Keep the legacy parameter-seeder fixture's layout in a temporary folder.
    # Physical source relocation must not change either active scoring workflow.
    fixture = tmp_path / "handover"
    for brand in ("moncler", "calvin_klein"):
        shutil.copytree(
            ROOT / "scripts/fmi-dossier/dossiers" / brand,
            fixture / "FMI_delivery/02_Brand_reports" / brand,
        )
    shutil.copytree(
        ROOT / "handover/FMI_delivery/04_Supporting_data",
        fixture / "FMI_delivery/04_Supporting_data",
    )
    updated, _ = align_dossiers(data, fixture)
    assert [b["id"] for b in updated["brands"]] == [b["id"] for b in data["brands"]]
    assert len(updated["brands"]) == 94
    assert sum(bool(b.get("invited")) for b in updated["brands"]) == sum(
        bool(b.get("invited")) for b in data["brands"]
    )
    moncler = next(b for b in updated["brands"] if b["id"] == "moncler")
    assert moncler["analysis"]["collection"] == "Grenoble FW2025"
    assert moncler["analysis"]["show_date"] == "2025-03-15"
    assert (
        moncler["analysis"]["dossier"]["financial"]["entities"]["moncler"]["scope"]
        == "retail_dtc"
    )
    ck = next(b for b in updated["brands"] if b["id"] == "calvin-klein")
    assert ck["analysis"]["show_date"] == "2025-09-12"
    assert (
        ck["analysis"]["dossier"]["financial"]["entities"]["calvin-klein"]["periods"][
            "oldest"
        ]["start"]
        == "2024-05-06"
    )


def test_dossier_handoff_uses_production_selection_without_mutation(dossier_case):
    from aily_project.services.fmi.data_handoff import build_handoff

    data, snapshot = dossier_case
    inputs = materialize(data)
    before = deepcopy((inputs, snapshot))
    report, records = build_handoff(inputs, snapshot, Policy())
    assert (inputs, snapshot) == before
    assert "1 prospects" in report
    assert "1 complete FMI" in report
    assert records["results"][0]["raw_fmi"] == pytest.approx(94)
    brand = records["prospects"][0]["financial"][0]
    assert brand["series_usable"]
    assert all(p["status"] == "selected_by_dossier_service" for p in brand["periods"])
    assert brand["periods"][-1]["selected_source_row_id"] == "B-2025"
    missing = records["prospects"][0]["financial"][-1]
    assert missing["entity_id"] == "missing"
    assert all(
        p["status"] == "missing_dossier_parameter_definition"
        for p in missing["periods"]
    )


def execute_fmi_notebook(name, namespace=None):
    """Exercise the active automated database notebooks with isolated clients."""
    namespace = namespace if namespace is not None else {}
    namespace.setdefault("display", lambda *args: None)
    path = ROOT / "scripts/fashion-momentum-index/notebooks" / name
    notebook = json.loads(path.read_text())
    for n, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "code":
            exec(compile("".join(cell["source"]), f"{name}:cell{n}", "exec"), namespace)
    return namespace


def save_notebook_snapshot(snapshot, folder):
    from runpy import run_path

    io = run_path(str(ROOT / "scripts/fashion-momentum-index/helpers.py"))
    for name in ("financials", "posts", "profiles", "registry", "overrides"):
        io["save_table"](getattr(snapshot, name), folder / name)
    io["save_table"]([snapshot.metadata], folder / "metadata")


@pytest.mark.parametrize("empty", [False, True])
def test_extraction_notebook_saves_source_and_transformed_tables(
    dossier_case, tmp_path, monkeypatch, empty
):
    from contextlib import contextmanager

    import pandas as pd

    from aily_project.services.fmi.extraction import DOCUMENT_RELATION, SPECS
    from aily_project.services.fmi.tasks.pipeline import save_json

    data, _ = dossier_case
    data.update(
        schema_version="fmi-input-v2",
        query={"first_year": 2023, "last_year": 2027, "row_limit": 100},
    )
    # A portfolio account absent from normalized tables exercises raw fallback.
    data["brands"][0]["analysis"]["dossier"]["social"]["members"] = [
        {
            "name": "Extra",
            "handle": "extra",
            "route": "show",
            "show_date": "2025-09-01",
            "timezone": "Europe/Paris",
        }
    ]
    input_file, data_dir = tmp_path / "inputs.json", tmp_path / "data"
    save_json(data, input_file)
    monkeypatch.setenv("FMI_INPUTS_PATH", str(input_file))
    monkeypatch.setenv("FMI_DATA_DIR", str(data_dir))
    events, calls = [], []

    class SourceReader:
        def fetch_data_as_df(self, query, *, bind_params=()):
            calls.append((query, bind_params))
            assert query.startswith("SELECT ")
            if "current_setting" in query:
                return pd.DataFrame(
                    [
                        {
                            "transaction_read_only": "on",
                            "default_transaction_read_only": "on",
                        }
                    ]
                )
            if "information_schema.columns" in query:
                return pd.DataFrame(
                    [
                        {
                            "table_schema": r.split(".")[0],
                            "table_name": r.split(".")[1],
                            "column_name": c,
                        }
                        for r, columns in SPECS.items()
                        for c in columns
                    ]
                )
            relation = query.split(" FROM ")[1].split(" WHERE ")[0]
            assert "WHERE" in query and "LIMIT %s" in query
            rows = []
            if not empty:
                if relation == "light.light_companies":
                    rows = [
                        {
                            "company_code": "B",
                            "company_name": "Brand",
                            "company_ticker": "BT",
                        }
                    ]
                elif relation.startswith(("light.", "ai.")):
                    rows = [
                        {
                            "company_code": "B",
                            "year": 2025,
                            "quarter": "Q2",
                            "type_filter_code": "revenue",
                            "type_filter_value": 123,
                        }
                    ]
                elif "financial_statements" in relation:
                    rows = [
                        {
                            "symbol": "BT",
                            "calendar_year": 2025,
                            "period": "Q2",
                            "revenue": 123,
                            "gross_profit": 60,
                            "reported_currency": "USD",
                        }
                    ]
                elif relation == "normalized.v_social_media_instagram_posts":
                    rows = [
                        {"profile_username": "brand", "post_id": "n", "like_count": 100}
                    ]
                elif (
                    relation == "denormalized.social_media_bright_data_instagram_posts"
                ):
                    assert "extra" in bind_params and "brand" not in bind_params
                    rows = [{"user_posted": "extra", "post_id": "f", "likes": 50}]
                elif relation == "normalized.social_media_instagram_profiles":
                    rows = [{"profile_username": "brand", "followers": 1000}]
                elif (
                    relation
                    == "denormalized.social_media_bright_data_instagram_profiles"
                ):
                    assert "extra" in bind_params and "brand" not in bind_params
                    rows = [{"account": "extra", "followers": 500}]
                elif relation == DOCUMENT_RELATION:
                    rows = [
                        {
                            "company_code": "BT",
                            "period_end": "2025-06-30",
                            "url": "https://example.com",
                        }
                    ]
            return pd.DataFrame(rows)

    def settings(**kwargs):
        events.append("settings")

    @contextmanager
    def connections():
        assert events == ["settings"]
        events.append("opened")
        try:
            yield SourceReader(), SourceReader()
        finally:
            events.append("closed")

    monkeypatch.setattr("aily_py_commons.aily_settings.AilySettings", settings)
    monkeypatch.setattr(
        "aily_project.services.fmi.connections.read_connections", connections
    )
    execute_fmi_notebook("01_extract.ipynb")
    from runpy import run_path

    io = run_path(str(ROOT / "scripts/fashion-momentum-index/helpers.py"))
    saved = io["read_snapshot"](data_dir / "extract")
    assert events == ["settings", "opened", "closed"]
    assert saved.metadata["authenticated"]
    assert (data_dir / "extract/schema.csv").exists()
    assert (data_dir / "extract/source-documents.csv").exists()
    assert io["load_table"](data_dir / "extract/queries")
    assert not list(data_dir.rglob("*.json"))
    for i, (query, _) in enumerate(calls):
        if " WHERE " in query and "information_schema" not in query:
            assert "current_setting" in calls[i - 1][0]
    if empty:
        assert saved.financials == [] and saved.posts == []
    else:
        raw = io["load_table"](
            data_dir / "extract/sources/light__light_financial_statements_actuals"
        )
        assert raw[0]["type_filter_value"] == 123 and "amount" not in raw[0]
        assert saved.financials[0]["amount"] == 123
        assert not saved.financials[0].get("scope")
        assert any(r["metric"] == "gross_profit" for r in saved.financials)
        assert {p["profile_username"] for p in saved.posts} == {"brand", "extra"}
        assert [p["followers_count"] for p in saved.profiles] == [1000, 500]


@pytest.mark.parametrize(
    "variant",
    [
        "complete",
        "missing_scope",
        "assumed",
        "comments",
        "company_trend",
        "published_growth",
        "percentile_reference",
        "percentile_weighted",
    ],
)
def test_visible_notebook_calculations_match_existing_method(
    dossier_case, tmp_path, monkeypatch, variant
):
    from aily_project.services.fmi.tasks.pipeline import save_json

    data, snapshot = dossier_case
    data["schema_version"] = "fmi-input-v2"
    method = data["brands"][0]["analysis"]["dossier"]
    if variant == "missing_scope":
        snapshot.financials[2]["scope"] = None
    elif variant == "assumed":
        method["trend"].update(basis="assumed", assumed_score=50)
    elif variant == "comments":
        method["social"]["metric"] = "comments"
    elif variant == "company_trend":
        method["trend"]["basis"] = "company_growth"
        snapshot.financials[5]["amount"] = 136.5
    elif variant == "published_growth":
        method["financial"]["growth_basis"] = "published_comparable_growth"
    elif variant.startswith("percentile_"):
        method["score_basis"] = "percentile"
        if variant == "percentile_weighted":
            data["headline_method"] = "weighted_components"
    inputs = materialize(data)
    expected = calculate(inputs, snapshot, Policy(), "comparison")[0][0].values
    input_file = tmp_path / "inputs.json"
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "outputs"
    save_json(data, input_file)
    save_notebook_snapshot(snapshot, data_dir / "extract")
    monkeypatch.setenv("FMI_INPUTS_PATH", str(input_file))
    monkeypatch.setenv("FMI_DATA_DIR", str(data_dir))
    monkeypatch.setenv("FMI_OUTPUT_DIR", str(output_dir))

    def no_cloud(*args, **kwargs):
        raise AssertionError("Scoring/delivery must stay offline")

    monkeypatch.setattr("aily_py_commons.aily_settings.AilySettings", no_cloud)
    workbook_rows = []

    def write_workbook(payload, path, **kwargs):
        workbook_rows.extend(payload["sheets"][0]["rows"])
        path.write_bytes(b"test workbook")

    monkeypatch.setattr(
        "aily_project.services.fmi.workbooks.write_workbook", write_workbook
    )
    execute_fmi_notebook("02_score.ipynb")
    delivered = execute_fmi_notebook("03_delivery.ipynb")
    actual = delivered["results"][0].values
    for key in (
        "earlier_growth",
        "latest_growth",
        "earlier_gap_pp",
        "latest_gap_pp",
        "used_peer_count",
        "used_peer_names",
        "used_peer_periods",
        "peer_calendar_alignment_status",
        "ir_score",
        "social_score",
        "trend_score",
        "raw_fmi",
        "display_fmi",
        "legacy_uplift_fraction",
        "uplift_fraction",
        "baseline_revenue",
        "legacy_adjusted_forecast",
        "adjusted_forecast",
        "fmi_status",
        "forecast_status",
    ):
        if isinstance(expected.get(key), (float, int)):
            assert actual.get(key) == pytest.approx(expected[key]), key
        elif expected.get(key) == "":
            assert actual.get(key) in (None, ""), key
        else:
            assert actual.get(key) == expected.get(key), key
    assert (data_dir / "score/peer-selection.csv").is_file()
    assert (data_dir / "score/social-post-selection.csv").is_file()
    assert (data_dir / "delivery/weighted-delivery.csv").is_file()
    assert not list(data_dir.rglob("*.json"))
    assert len(workbook_rows) == 1
    assert (
        json.loads((output_dir / "weighted-delivery.json").read_text()) == workbook_rows
    )


def test_delivery_replaces_missing_scores_without_touching_dossiers(
    dossier_case, tmp_path, monkeypatch
):
    from aily_project.services.fmi.tasks.pipeline import save_json

    data, snapshot = dossier_case
    data["schema_version"] = "fmi-input-v2"
    for row in snapshot.financials:
        row["scope"] = None
    input_file, data_dir = tmp_path / "inputs.json", tmp_path / "data"
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    (output_dir / "weighted-delivery.xlsx").write_bytes(b"old workbook")
    (output_dir / "weighted-delivery.json").write_text('[{"raw_fmi": 99}]')
    dossier = output_dir / "dossier-delivery.xlsx"
    dossier.write_bytes(b"unchanged dossier")
    protected = {
        output_dir / "dossier-calculated-delivery.xlsx": b"calculated dossier",
        output_dir / "dossier-calculated-delivery.json": b"calculated dossier JSON",
        tmp_path / "dossier-input.xlsx": b"one-time dossier input",
    }
    for path, content in protected.items():
        path.write_bytes(content)
    save_json(data, input_file)
    save_notebook_snapshot(snapshot, data_dir / "extract")
    monkeypatch.setenv("FMI_INPUTS_PATH", str(input_file))
    monkeypatch.setenv("FMI_DATA_DIR", str(data_dir))
    monkeypatch.setenv("FMI_OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("FMI_DOSSIER_OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("FMI_DOSSIER_INPUTS_PATH", str(tmp_path / "dossier-input.xlsx"))

    def write_workbook(payload, path, **kwargs):
        assert len(payload["sheets"][0]["rows"]) == 1
        path.write_bytes(b"new workbook")

    monkeypatch.setattr(
        "aily_project.services.fmi.workbooks.write_workbook", write_workbook
    )
    execute_fmi_notebook("02_score.ipynb")
    execute_fmi_notebook("03_delivery.ipynb")
    rows = json.loads((output_dir / "weighted-delivery.json").read_text())
    assert rows[0]["raw_fmi"] is None and rows[0]["social_score"] is not None
    assert rows[0]["missing_reasons"]
    assert (output_dir / "weighted-delivery.xlsx").read_bytes() == b"new workbook"
    assert dossier.read_bytes() == b"unchanged dossier"
    assert all(path.read_bytes() == content for path, content in protected.items())


@pytest.mark.parametrize(
    "change,status,count",
    [
        ("scope", "observed_candidates_not_verified_or_conflicting", 1),
        ("no_rows", "no_actual_observations_in_snapshot", 0),
        ("other_end", "no_native_end_hint_in_snapshot", 0),
        ("no_identifier", "missing_source_identifier", 0),
    ],
)
def test_dossier_inventory_distinguishes_metadata_rows_and_mapping(
    dossier_case, change, status, count
):
    from aily_project.services.fmi.dossier_coverage import financial_inventory

    data, snapshot = dossier_case
    if change == "scope":
        snapshot.financials[2]["scope"] = None
    elif change == "no_rows":
        snapshot.financials = [
            r for r in snapshot.financials if r["company_code"] != "B"
        ]
    elif change == "other_end":
        snapshot.financials[2]["period_end"] = "2025-06-29"
    else:
        data["brands"][0].pop("light_code")
        data["brands"][0].pop("ticker")
    inputs = materialize(data)
    row = financial_inventory(inputs, snapshot, inputs.analyses[0])[0]["periods"][-1]
    assert row["status"] == status
    assert row["native_end_hint_count"] == count
    assert row["selected_source_row_id"] is None
    if change == "scope":
        assert row["actual_observation_count"] == 3
        assert row["missing_raw_semantics_counts"]["scope"] == 1


def test_document_hints_never_create_financial_measurements(dossier_case):
    from aily_project.services.fmi.dossier_coverage import financial_inventory

    data, snapshot = dossier_case
    snapshot.financials = []
    snapshot.metadata["financial_source_documents"] = [
        {
            "company_code": "B",
            "period_start": "2025-04-01",
            "period_end": "2025-06-30",
            "url": "https://issuer.example/q2.pdf",
        },
        {"company_code": "UNRELATED", "period_end": "2025-06-30"},
    ]
    inputs = materialize(data)
    entity = financial_inventory(inputs, snapshot, inputs.analyses[0])[0]
    row = entity["periods"][-1]
    assert row["status"] == "source_documents_present_measurement_adapter_required"
    assert row["document_end_hint_count"] == 1
    assert len(row["document_candidates"]) == 1
    assert row["actual_observation_count"] == 0
    assert not entity["series_usable"]
    assert (
        calculate(inputs, snapshot, Policy(), "documents")[0][0].values.get("raw_fmi")
        is None
    )


def test_dossier_inventory_preserves_explicit_subject_routing(dossier_case):
    from aily_project.services.fmi.dossier_coverage import financial_inventory

    data, snapshot = dossier_case
    data["peer_entities"].append({"id": "parent", "name": "Parent", "light_code": "P"})
    spec = data["brands"][0]["analysis"]["dossier"]["financial"]["entities"]["brand"]
    spec.update(source_entity_id="parent", subject="Parent")
    inputs = materialize(data)
    entity = financial_inventory(inputs, snapshot, inputs.analyses[0])[0]
    assert entity["source_entity_id"] == "parent"
    assert entity["light_code"] == "P"
    assert entity["periods"][-1]["selected_source_row_id"] == "P-2025"


def test_native_end_hint_does_not_infer_fiscal_equivalence(dossier_case):
    from aily_project.services.fmi.dossier_coverage import native_end_hint

    _, snapshot = dossier_case
    row = snapshot.financials[2]
    assert not native_end_hint(row, {"label": "FY2025", "type": "annual"})
    assert not native_end_hint(row, {"end": "invalid"})
    assert not native_end_hint(row, {"end": "2025-06-29"})
    assert native_end_hint(
        row, {"end": "2025-06-29", "alignment": "calendar_selling_window_proxy"}
    )


def test_dossier_handoff_cli_is_offline_and_preserves_input_files(
    dossier_case, tmp_path, monkeypatch
):
    from dataclasses import asdict

    from click.testing import CliRunner

    from aily_project.cli import cli
    from aily_project.services.fmi import runner
    from aily_project.services.fmi.tasks.pipeline import save_json

    data, snapshot = dossier_case
    data["schema_version"] = "fmi-input-v2"
    snapshot.metadata["resolved_policy"] = Policy().model_dump()
    snapshot.metadata["row_limit"] = 10
    snapshot.metadata["queries"] = []
    source = tmp_path / "snapshot.json"
    inputs = tmp_path / "inputs.json"
    output = tmp_path / "audit.md"
    save_json(asdict(snapshot), source)
    save_json(data, inputs)
    before = source.read_bytes(), inputs.read_bytes()

    def no_cloud():
        raise AssertionError("Offline diagnostic must not initialize cloud settings")

    monkeypatch.setattr(runner, "initialize", no_cloud)
    result = CliRunner().invoke(
        cli,
        [
            "fmi",
            "data-handoff",
            "--inputs",
            str(inputs),
            "--snapshot",
            str(source),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert (source.read_bytes(), inputs.read_bytes()) == before
    assert "FMI dossier source-coverage audit" in output.read_text()
    assert output.with_suffix(".sql").exists()
    records = json.loads((tmp_path / "data-handoff-results.json").read_text())
    assert records["results"][0]["raw_fmi"] == pytest.approx(94)
