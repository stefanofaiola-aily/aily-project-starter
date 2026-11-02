"""Source adapters and immutable dossier refresh, without database access."""

from copy import deepcopy
from datetime import date

import pytest

from aily_project.services.fmi.dossier_selection import annual_from_quarters, series
from aily_project.services.fmi.dossiers import refresh_comparisons
from aily_project.services.fmi.issuer_measurements import decode, matches_subject
from aily_project.services.fmi.models import Inputs, Snapshot
from aily_project.services.fmi.policy import Policy

pytestmark = pytest.mark.unit


def document(code, host, content, **kwargs):
    return {
        "company_code": code,
        "url": f"https://{host}/results.pdf",
        "content": content,
        "period_end": "2025-12-31",
        **kwargs,
    }


LVMH = (
    "Change in revenue by business group ( EUR millions and percentage) "
    "2025 2024 2025/2024 Change 2023 Published Organic (a) "
    "Fashion and Leather Goods 37,770 41,060 -8% -5% 42,169 "
    "Total 80,807 84,683 -5% -1% 86,153 "
    "Profit from recurring operations Fashion and Leather Goods 13,209 15,230 16,836"
)


def test_lvmh_revenue_not_operating_profit_and_distinct_scopes():
    rows = decode(document("LVMHF", "lvmh.com", LVMH))
    assert len(rows) == 6
    group = [r for r in rows if r["scope"] == "consolidated"]
    assert [r["amount"] for r in group] == [80807e6, 84683e6, 86153e6]
    assert (
        group[0]["unit_multiplier"] == 1 and group[0]["source_unit_multiplier"] == 1e6
    )
    assert matches_subject(
        group[0], {"subject": "LVMH consolidated group", "scope": "consolidated"}
    )
    assert not matches_subject(
        group[0],
        {"subject": "LVMH Fashion and Leather Goods", "scope": "parent_segment"},
    )
    assert rows[0]["source_url"] and rows[0]["source_row_id"] and rows[0]["evidence"]
    assert rows[0]["available_at"] is None and not rows[0]["vintage_verified"]


def test_prada_scale_requires_explicit_units_complete_content_and_issuer_host():
    text = (
        "Key economic indicators (amounts in thousands of Euro) "
        "twelve months ended December 31 2025 twelve months ended December 31 2024 "
        "Net revenues 5,717,521 5,431,557"
    )
    rows = decode(document("PRDSY", "pradagroup.com", text))
    assert rows[0]["amount"] == 5717521e3 and rows[1]["amount"] == 5431557e3
    assert (
        decode(
            document("PRDSY", "pradagroup.com", text.replace("thousands", "millions"))
        )
        == []
    )
    assert decode(document("PRDSY", "unverified.com", text)) == []
    assert (
        decode(document("PRDSY", "pradagroup.com", text, content_length=len(text) + 1))
        == []
    )


def test_pvh_discrete_brand_quarters_not_six_months_or_parent():
    rows = decode(
        document(
            "PVH",
            "pvh.com",
            "Consolidated GAAP Statements of Operations "
            "(In millions, except per share data) "
            "REVENUE BY BRAND Quarter Ended Six Months Ended "
            "8/2/26 8/3/25 8/2/26 8/3/25 "
            "Tommy Hilfiger $ 1,131.8 $ 1,135.9 $ 2,209.1 $ 2,184.0 "
            "Calvin Klein 913.3 980.0 1,808.5 1,866.1 Total Revenue 2097.0",
        )
    )
    assert len(rows) == 4
    ck = [r for r in rows if r["financial_subject"] == "Calvin Klein"]
    assert ck[0]["amount"] == 913.3e6
    assert (ck[0]["period_start"], ck[0]["period_end"]) == (
        date(2026, 5, 4),
        date(2026, 8, 2),
    )
    assert not matches_subject(ck[0], {"subject": "PVH", "scope": "consolidated"})


def test_moncler_annual_not_comparison_year_or_quarter():
    text = (
        "2023 GROUP REVENUES. GROUP CONSOLIDATED REVENUES : "
        "EUR 2, 984.2 million compared with EUR 2,602.9 million in 2022."
    )
    rows = decode(
        document("MONC.MI", "monclergroup.com", text, period_end="2023-12-31")
    )
    assert rows[0]["period_end"] == date(2023, 12, 31) and rows[0]["amount"] == 2984.2e6
    assert (
        decode(document("MONC.MI", "monclergroup.com", text, period_end="2023-03-31"))
        == []
    )


def test_tapestry_annual_brand_sales_not_quarter_parent_or_gross_profit():
    text = (
        "DETAIL TO NET SALES For the Quarter and Year Ended (in millions) "
        "QUARTER ENDED June 27, 2026 June 28, 2025 Coach $ 1641.5 $ 1425.1 "
        "YEAR ENDED June 27, 2026 June 28, 2025 % Change Constant Currency % Change "
        "Coach $ 6,914.7 $ 5,598.5 24% 23% Kate Spade 1,074.9 1,197.1 (10)% (11)% "
        "Total Tapestry 8,004.2 7,010.7 Schedules 3 & 4 Gross Profit Coach 1400"
    )
    rows = decode(document("TPR", "tapestry.gcs-web.com", text))
    assert [r["amount"] for r in rows] == [6914.7e6, 5598.5e6, 1074.9e6, 1197.1e6]
    assert rows[0]["period_start"] == date(2025, 6, 29)
    assert rows[0]["fiscal_year_label"] == "FY2026"
    assert rows[0]["period_boundaries_verified"]
    assert not rows[1]["period_boundaries_verified"]
    assert not matches_subject(
        rows[0], {"subject": "Tapestry", "scope": "consolidated"}
    )
    assert (
        decode(
            document(
                "TPR",
                "tapestry.gcs-web.com",
                text.replace("in millions", "in thousands"),
            )
        )
        == []
    )


def test_capri_annual_michael_kors_not_quarter_or_disposed_versace_group():
    text = (
        "CONSOLIDATED REVENUE DATA ($ in millions) (Unaudited) "
        "Three Months Ended Fiscal Years Ended March 28, 2026 March 29, 2025 "
        "March 28, 2026 March 29, 2025 Revenue by Segment and Region: "
        "Michael Kors Revenue 656 694 2,874 3,016 "
        "Total Capri Revenue $ 796 $ 827 $ 3,474 $ 3,621 SCHEDULE 4"
    )
    rows = decode(document("CPRI", "s21.q4cdn.com", text))
    assert [r["amount"] for r in rows] == [2874e6, 3016e6]
    assert rows[0]["period_start"] == date(2025, 3, 30)
    assert all(r["scope"] == "brand_segment" for r in rows)
    assert not matches_subject(
        rows[0], {"subject": "Capri Holdings", "scope": "consolidated"}
    )


def test_gap_reported_53_week_year_not_quarter_or_calendar_year():
    text = (
        "CONSOLIDATED STATEMENTS OF OPERATIONS UNAUDITED "
        "13 Weeks Ended 14 Weeks Ended (1) 52 Weeks Ended 53 Weeks Ended (1) "
        "($ and shares in millions except per share amounts) "
        "February 1, 2025 February 3, 2024 February 1, 2025 February 3, 2024 "
        "Net sales $ 4,149 $ 4,298 $ 15,086 $ 14,889"
    )
    rows = decode(document("GAP", "s204.q4cdn.com", text))
    assert [r["amount"] for r in rows] == [15086e6, 14889e6]
    assert rows[1]["period_start"] == date(2023, 1, 29)
    assert rows[1]["fiscal_year_label"] == "FY2023"
    assert rows[1]["period_boundaries_verified"]
    assert (
        decode(document("GAP", "s204.q4cdn.com", text.replace("52 Weeks", "26 Weeks")))
        == []
    )


def test_abercrombie_annual_consolidated_not_brand_or_quarter():
    text = (
        "Consolidated Statements of Operations (in thousands, except per share data) "
        "(Unaudited) Fifty-Two Weeks Ended Fifty-Three Weeks Ended "
        "February 1, 2025% of Net Sales February 3, 2024% of Net Sales "
        "Net sales $ 4,948,587 100.0 % $ 4,280,677 100.0 %"
    )
    rows = decode(document("ANF", "corporate.abercrombie.com", text))
    assert rows[0]["amount"] == 4948587e3
    assert rows[1]["period_start"] == date(2023, 1, 29)
    assert not matches_subject(
        rows[0], {"subject": "Abercrombie", "scope": "brand_segment"}
    )
    assert (
        decode(
            document(
                "ANF",
                "corporate.abercrombie.com",
                text.replace("Fifty-Two", "Thirteen"),
            )
        )
        == []
    )


def test_ralph_lauren_annual_not_fourth_quarter():
    text = (
        "CONSOLIDATED STATEMENTS OF OPERATIONS (Unaudited) "
        "Three Months Ended Twelve Months Ended March 28, 2026 March 29, 2025 "
        "March 28, 2026 March 29, 2025 (millions, except per share data) "
        "Net revenues $ 1,978.7 $ 1,697.3 $ 8,114.5 $ 7,079.0"
    )
    rows = decode(document("RL", "ralphlauren.com", text))
    assert [r["amount"] for r in rows] == [8114.5e6, 7079e6]
    assert rows[0]["fiscal_year_label"] == "FY2026"
    assert rows[0]["period_start"] == date(2025, 3, 30)


def test_moncler_discrete_dtc_not_ytd_stone_island_or_group():
    header = "Q1 25 vs 24 Q2 25 vs 24 Q3 25 vs 24 Q4 25 vs 24 "
    units = "EUR m " + "2025 2024 cFX " * 4
    text = (
        header + units + "DTC 630.5 608.5 4% 252.7 267.3 (1%) 372.3 384.3 0% "
        "1,104.2 1,071.9 7% WHOLESALE 91.3 96.5 (5%) MONCLER 721.8 "
        + header
        + units
        + "DTC 55.3 49.4 12% 43.9 43.2 3% 46.0 43.1 11% 81.3 73.2 16% "
        "WHOLESALE 52.0 63.6 (19%) STONE ISLAND 107.3 "
    )
    rows = decode(document("MONC.MI", "monclergroup.com", text))
    assert len(rows) == 8
    assert all(r["financial_subject"] == "Moncler" for r in rows)
    assert rows[-2]["amount"] == 1104.2e6
    assert rows[-2]["period_start"] == date(2025, 10, 1)
    assert rows[-2]["period_end"] == date(2025, 12, 31)
    assert rows[-2]["period_boundaries_verified"]
    ytd = text.replace(
        "Q2 25 vs 24 Q3 25 vs 24 Q4 25 vs 24", "H1 25 vs 24 9M 25 vs 24 FY 25 vs 24"
    )
    assert decode(document("MONC.MI", "monclergroup.com", ytd)) == []
    mismatched_years = text.replace("2025 2024 cFX", "2024 2023 cFX")
    assert decode(document("MONC.MI", "monclergroup.com", mismatched_years)) == []


def test_burberry_retail_explicit_weeks_split_digits_and_reported_fx():
    text = (
        "RETAIL REVENUE 13 WEEKS ENDED 27 JUNE 2026 "
        "27 June 2 8 June % change £ million 202 6 202 5 Reported FX CER * "
        "Retail revenue 4 55 433 5 % 4 % Comparable store sales 4%"
    )
    rows = decode(document("BRBY.L", "burberryplc.com", text))
    assert [r["amount"] for r in rows] == [455e6, 433e6]
    assert rows[0]["scope"] == "retail_dtc" and rows[0]["currency"] == "GBP"
    assert rows[0]["period_start"] == date(2026, 3, 29)
    assert rows[1]["period_end"] == date(2025, 6, 28)
    assert rows[0]["period_boundaries_verified"]
    assert (
        decode(
            document("BRBY.L", "burberryplc.com", text.replace("13 WEEKS", "26 WEEKS"))
        )
        == []
    )
    assert (
        decode(
            document(
                "BRBY.L", "burberryplc.com", text.replace("£ million", "£ thousand")
            )
        )
        == []
    )


def test_rl_retail_totals_not_wholesale_or_consolidated_and_no_annual_inference():
    text = (
        "NET REVENUES BY SALES CHANNEL (Unaudited) Three Months Ended "
        "June 27, 2026 June 28, 2025 North America Europe Asia Other Total "
        "North America Europe Asia Other Total (millions) Sales Channel: "
        "Retail $503.2 $294.9 $571.2 $— $1,369.3 "
        "$461.0 $285.8 $454.4 $— $1,201.2 Wholesale 237.1 299.5 18.1 — 554.7 "
        "Net revenues 1959.8"
    )
    rows = decode(document("RL", "investor.ralphlauren.com", text))
    assert [r["amount"] for r in rows] == [1369.3e6, 1201.2e6]
    assert all(r["scope"] == "retail_dtc" for r in rows)
    assert rows[0]["period_start"] == date(2026, 3, 29)
    assert not rows[0]["period_boundaries_verified"]
    assert annual_from_quarters(rows, date(2026, 1, 1), date(2026, 12, 31)) is None
    assert (
        decode(
            document(
                "RL", "investor.ralphlauren.com", text.replace("1,369.3", "1,959.8")
            )
        )[0]["amount"]
        == 1201.2e6
    )
    assert (
        decode(
            document(
                "RL",
                "investor.ralphlauren.com",
                text.replace("Three Months", "Six Months"),
            )
        )
        == []
    )


def test_hermes_alias_and_kering_brand_segments():
    rows = decode(
        document(
            "hermes",
            "assets-finance.hermes.com",
            "CONSOLIDATED INCOME STATEMENT In millions of euros "
            "2025 2024 Revenue 16,002 15,170 Cost of sales",
        )
    )
    assert rows[0]["amount"] == 16002e6
    assert matches_subject(rows[0], {"subject": "Hermes", "scope": "consolidated"})
    rows = decode(
        document(
            "KER.PA",
            "kering.com",
            "Revenue (in € million) 2025 2024 Reported change Comparable change (1) "
            "Gucci 5,992 7,650 -22% -19% Yves Saint Laurent 2,643 2,881 -8% -6% "
            "Recurring operating income (in € million) 2025 2024 Change "
            "Gucci 966 1,605",
        )
    )
    assert len(rows) == 4 and rows[0]["amount"] == 5992e6
    assert matches_subject(
        rows[2], {"subject": "Saint Laurent", "scope": "brand_segment"}
    )
    assert not matches_subject(rows[0], {"subject": "Kering", "scope": "consolidated"})


def test_source_series_restores_explicit_segment_without_using_parent_total():
    rows = decode(document("LVMHF", "lvmh.com", LVMH))
    entity = {"entity_id": "dior", "name": "Dior"}
    spec = {
        "subject": "LVMH Fashion and Leather Goods",
        "scope": "parent_segment",
        "periods": {
            role: {"start": f"{y}-01-01", "end": f"{y}-12-31", "type": "annual"}
            for role, y in zip(
                ("oldest", "earlier", "latest"), (2023, 2024, 2025), strict=True
            )
        },
    }
    analysis = {
        "analysis_id": "a",
        "dossier": {"financial": {"entities": {"dior": spec}}},
    }
    snapshot = Snapshot(
        financials=rows, metadata={"extracted_at": "2026-11-02T00:00:00Z"}
    )
    selected, missing = series(Inputs(entities=[entity]), entity, snapshot, analysis)
    assert not missing and len(selected) == 3
    assert selected[2]["amount"] == 37770e6 and selected[2]["scope"] == "parent_segment"
    conflict = deepcopy(rows[0])
    conflict.update(amount=1, source_row_id="conflict")
    snapshot.financials.append(conflict)
    _, missing = series(Inputs(entities=[entity]), entity, snapshot, analysis)
    assert any("conflicting" in r for r in missing)
    native = {
        "kind": "actual",
        "metric": "revenue",
        "amount": 1,
        "source_relation": "normalized.finance_fmp_financial_statements",
    }
    assert not matches_subject(native, spec)


def test_refresh_only_comparison_columns_and_clear_stale_metrics():
    reference = {
        "brand_id": "b",
        "dossier_headline_fmi": 61.2,
        "dossier_original_raw_fmi": 61.2,
        "dossier_ir_score": 34.5,
        "dossier_social_score": 100,
        "dossier_trend_score": 70,
        "dossier_component_sum": 61.25,
        "dossier_scenario_uplift_fraction": 0.01,
        "name": "Original name",
        "run_id": "original",
        "baseline_revenue": 123,
        "current_raw_fmi": 99,
        "current_ir_score": 99,
        "current_social_score": 99,
        "current_missing_inputs": None,
        "comparison_raw_difference": 99,
        "comparison_ir_difference": 99,
    }
    original = deepcopy(reference)
    rows = refresh_comparisons(
        [reference],
        [
            {
                "brand_id": "b",
                "raw_fmi": None,
                "ir_score": 40,
                "missing_reasons": "missing social",
            }
        ],
        Policy(),
    )
    assert reference == original
    assert (
        rows[0]["current_ir_score"] == 40 and rows[0]["comparison_ir_difference"] == 5.5
    )
    assert (
        rows[0]["current_raw_fmi"] is None and rows[0]["current_social_score"] is None
    )
    for k, v in original.items():
        if not k.startswith(("current_", "comparison_")):
            assert rows[0][k] == v
    with pytest.raises(ValueError, match="unique"):
        refresh_comparisons(
            [reference], [{"brand_id": "b"}, {"brand_id": "b"}], Policy()
        )
