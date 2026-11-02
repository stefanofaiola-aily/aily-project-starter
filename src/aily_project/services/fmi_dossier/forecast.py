"""Optional, narrowly scoped Light forecast lookup for dossier-only baselines."""

import calendar
import hashlib
import json
import math
import unicodedata
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from .model import Row, clean


class Reader(Protocol):
    def fetch_data_as_df(
        self, query: str, *, bind_params: tuple[Any, ...] = ()
    ) -> Any: ...


def verify_read_only(client: Reader) -> None:
    rows = client.fetch_data_as_df(
        "SELECT current_setting('transaction_read_only') AS transaction_read_only, "
        "current_setting('default_transaction_read_only') "
        "AS default_transaction_read_only"
    ).to_dict("records")
    if len(rows) != 1 or any(
        rows[0].get(k) != "on"
        for k in ("transaction_read_only", "default_transaction_read_only")
    ):
        raise ValueError(
            "Dossier forecast lookup requires a verified read-only session"
        )


def _name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(c for c in text.lower() if c.isascii() and c.isalnum())


def select_scenario_forecast(
    observations: list[Row], start: date, end: date, as_of: date
) -> Row:
    """Current demo horizon: Q4-period end, nearby fiscal Q4, then three months.

    Quarterly rows remain single native amounts, never summed or split into
    months. Monthly fallback requires three explicit, complete monthly amounts.
    Fiscal proxy start dates are calendar-month alignment, not claimed source
    boundaries. No historical-vintage claim is made.
    """
    if start > end:
        raise ValueError("Forecast start must not follow end")
    eligible = [
        r
        for r in observations
        if r.get("type_filter_code") == "revenue"
        and isinstance(r.get("type_filter_value"), (int, float))
        and not isinstance(r["type_filter_value"], bool)
        and math.isfinite(r["type_filter_value"])
        and r["type_filter_value"] > 0
    ]
    quarters = [r for r in eligible if r.get("quarter") in {"Q1", "Q2", "Q3", "Q4"}]
    current = [
        r
        for r in quarters
        if abs((date.fromisoformat(str(r["reported_date"])[:10]) - end).days) <= 7
        and date.fromisoformat(str(r["reported_date"])[:10]) >= as_of
    ]
    method = "quarter_ending_in_requested_q4_window"
    if not current:
        method = "native_fiscal_q4_proxy"
        current = [
            r
            for r in quarters
            if r["quarter"] == "Q4"
            and max(start, as_of)
            <= date.fromisoformat(str(r["reported_date"])[:10])
            <= end + timedelta(days=38)
        ]
    if current:
        # Multiple matching native periods or conflicting source amounts need
        # a choice, not arbitrary first-row selection or summation.
        distinct = {
            (
                str(r["reported_date"])[:10],
                r["year"],
                r["quarter"],
                r["type_filter_value"],
            ): r
            for r in current
        }
        if len(distinct) != 1:
            return {
                "status": "conflicting_current_quarter_forecasts",
                "observations": current,
            }
        selected = next(iter(distinct.values()))
        closing = date.fromisoformat(str(selected["reported_date"])[:10])
        aligned_closing = closing - timedelta(days=7) if closing.day <= 7 else closing
        aligned_month = aligned_closing.year * 12 + aligned_closing.month - 1 - 2
        fiscal_start = date(aligned_month // 12, aligned_month % 12 + 1, 1)
        return {
            "status": "available_current_demo_forecast",
            "method": method,
            "observations": [selected],
            "amount": selected["type_filter_value"],
            "target_start": start.isoformat()
            if method.startswith("quarter_ending")
            else fiscal_start.isoformat(),
            "target_end": end.isoformat()
            if method.startswith("quarter_ending")
            else closing.isoformat(),
            "period_start_basis": "requested_calendar_window"
            if method.startswith("quarter_ending")
            else "three_calendar_month_proxy_not_verified_native_start",
        }
    # The current month plus two is an explicit demo convention (Nov–Jan on
    # 2 Nov 2026). Only records labelled grain=monthly qualify for summation.
    months = [(as_of.year * 12 + as_of.month - 1 + i) for i in range(3)]
    retained = []
    for month in months:
        candidates = [
            r
            for r in eligible
            if r.get("grain") == "monthly"
            and date.fromisoformat(str(r["reported_date"])[:10]).year * 12
            + date.fromisoformat(str(r["reported_date"])[:10]).month
            - 1
            == month
        ]
        unique = {
            (str(r["reported_date"])[:7], r["type_filter_value"]): r for r in candidates
        }
        if len(unique) != 1:
            return {
                "status": "missing_or_conflicting_three_month_forecast",
                "observations": retained + candidates,
            }
        retained.append(next(iter(unique.values())))
    last_year, last_month = months[-1] // 12, months[-1] % 12 + 1
    if any(
        len({r.get(k) for r in retained}) != 1
        for k in ("company_code", "currency", "unit_multiplier", "scope")
    ):
        return {
            "status": "incompatible_monthly_forecast_basis",
            "observations": retained,
        }
    return {
        "status": "available_current_demo_forecast",
        "method": "current_and_next_two_complete_months",
        "observations": retained,
        "amount": sum(r["type_filter_value"] for r in retained),
        "target_start": date(as_of.year, as_of.month, 1).isoformat(),
        "target_end": date(
            last_year, last_month, calendar.monthrange(last_year, last_month)[1]
        ).isoformat(),
        "period_start_basis": "complete_monthly_source_periods",
    }


def query_missing(
    rows: list[Row], client: Reader, start: date, end: date
) -> tuple[list[Row], list[Row]]:
    """Preserve approved dossier amounts and all financial/social score components.

    Dates are requested scenario dates, not invented fiscal-calendar alignment.
    Native candidates stay diagnostic until scope/units/alignment are confirmed.
    """
    if start > end:
        raise ValueError("Forecast start must not follow end")
    verify_read_only(client)
    schema = client.fetch_data_as_df(
        "SELECT table_schema, table_name, column_name FROM information_schema.columns "
        "WHERE (table_schema = 'light' AND table_name = 'light_companies') "
        "OR (table_schema = 'ai' "
        "AND table_name = 'light_financial_statements_forecast') "
        "ORDER BY table_schema, table_name, ordinal_position LIMIT 300"
    ).to_dict("records")
    columns: dict[str, set[str]] = {}
    for item in schema:
        columns.setdefault(item["table_schema"] + "." + item["table_name"], set()).add(
            item["column_name"]
        )
    forecast_relation = "ai.light_financial_statements_forecast"
    company_relation = "light.light_companies"
    required = {
        "company_code",
        "reported_date",
        "year",
        "quarter",
        "type_filter_code",
        "type_filter_value",
    }
    if not required <= columns.get(forecast_relation, set()):
        raise ValueError("Light forecast schema missing required columns")
    if not {"company_code", "company_name", "company_ticker"} <= columns.get(
        company_relation, set()
    ):
        raise ValueError("Light company schema missing required columns")
    pulled_at = datetime.now(UTC).isoformat()
    results, audit = [], []
    for source in rows:
        row = dict(source)
        results.append(row)
        if (
            row.get("baseline_revenue") is not None
            and row.get("baseline_approved") is True
        ) or not row.get("include"):
            row["forecast_lookup_status"] = (
                "not_requested_existing_dossier_baseline_or_excluded"
            )
            continue
        if not row.get("source_document"):
            row["forecast_lookup_status"] = "no_dossier_source_no_forecast_lookup"
            continue
        subject = (
            row.get("baseline_subject") or row.get("financial_subject") or row["name"]
        )
        requested_code = (
            row.get("baseline_company_code")
            or row.get("company_code")
            or row.get("light_code")
        )
        company_keys = ["company_code", "company_name", "company_ticker"]
        company_keys += [
            k
            for k in ("company_currency", "currency")
            if k in columns[company_relation]
        ]
        companies = client.fetch_data_as_df(
            "SELECT "
            + ", ".join(company_keys)
            + " FROM "
            + company_relation
            + " WHERE company_code = %s OR company_ticker = %s "
            "OR lower(company_name) = lower(%s) LIMIT 51",
            bind_params=(requested_code, row.get("ticker"), subject),
        ).to_dict("records")
        if len(companies) > 50:
            raise ValueError("Company lookup exceeded bound")
        exact = [c for c in companies if c["company_code"] == requested_code]
        if not exact:
            exact = [c for c in companies if _name(c["company_name"]) == _name(subject)]
        if len(exact) != 1:
            row["forecast_lookup_status"] = "company_mapping_missing_or_ambiguous"
            row["forecast_lookup_company_candidates"] = clean(companies)
            continue
        company = exact[0]
        target_start = date.fromisoformat(
            row.get("forecast_target_start") or start.isoformat()
        )
        target_end = date.fromisoformat(
            row.get("forecast_target_end") or end.isoformat()
        )
        selected_columns = [
            "company_code",
            "reported_date",
            "year",
            "quarter",
            "type_filter_code",
            "type_filter_value",
        ]
        selected_columns += [
            k
            for k in (
                "scope",
                "unit_multiplier",
                "currency",
                "period_start",
                "period_end",
                "forecast_vintage",
            )
            if k in columns[forecast_relation]
        ]
        query = (
            "SELECT "
            + ", ".join(selected_columns)
            + " FROM "
            + forecast_relation
            + (
                " WHERE company_code = %s AND type_filter_code = 'revenue' "
                "AND reported_date BETWEEN %s AND %s "
                "ORDER BY reported_date, year, quarter LIMIT 201"
            )
        )
        candidates = clean(
            client.fetch_data_as_df(
                query, bind_params=(company["company_code"], target_start, target_end)
            ).to_dict("records")
        )
        if len(candidates) > 200:
            raise ValueError("Forecast lookup exceeded row bound")
        for candidate in candidates:
            candidate.update(
                source_relation=forecast_relation,
                source_row_id=hashlib.sha256(
                    json.dumps(candidate, sort_keys=True).encode()
                ).hexdigest(),
                extracted_at=pulled_at,
                brand_id=row["brand_id"],
            )
        audit.append(
            {
                "brand_id": row["brand_id"],
                "query": query,
                "scope": clean([company["company_code"], target_start, target_end]),
                "extracted_at": pulled_at,
                "candidates": candidates,
            }
        )
        row.update(
            forecast_lookup_company_code=company["company_code"],
            forecast_lookup_subject=company["company_name"],
            forecast_lookup_target_start=target_start.isoformat(),
            forecast_lookup_target_end=target_end.isoformat(),
            forecast_lookup_extracted_at=pulled_at,
            forecast_lookup_candidates=candidates,
        )
        exact_end = [
            c
            for c in candidates
            if str(c.get("period_end") or c["reported_date"])[:10]
            == target_end.isoformat()
        ]
        if not exact_end:
            row["forecast_lookup_status"] = "no_exact_native_target_end_forecast"
            continue
        distinct = {
            json.dumps({k: c.get(k) for k in selected_columns}, sort_keys=True): c
            for c in exact_end
        }
        if len(distinct) != 1:
            row["forecast_lookup_status"] = "conflicting_native_forecast_candidates"
            continue
        candidate = next(iter(distinct.values()))
        amount = candidate.get("type_filter_value")
        if (
            isinstance(amount, bool)
            or not isinstance(amount, (float, int))
            or not math.isfinite(amount)
            or amount <= 0
        ):
            row["forecast_lookup_status"] = "invalid_forecast_amount"
            continue
        row.update(
            forecast_candidate_revenue=amount,
            forecast_candidate_period=(
                f"Light native {candidate['year']} {candidate['quarter']}"
            ),
        )
        # Explicit review covers native period boundaries, unadjusted status and
        # reporting perimeter. Never equate dossier units with Light native units.
        native_scale = candidate.get("unit_multiplier") or row.get(
            "forecast_native_unit_multiplier"
        )
        scale = row.get("baseline_unit_multiplier")
        row["forecast_candidate_unit_multiplier"] = native_scale
        if (
            isinstance(native_scale, (float, int))
            and not isinstance(native_scale, bool)
            and native_scale > 0
            and isinstance(scale, (float, int))
            and not isinstance(scale, bool)
            and scale > 0
        ):
            row["forecast_candidate_baseline_revenue"] = amount * native_scale / scale
        scope = candidate.get("scope") or row.get("baseline_scope")
        currency = (
            candidate.get("currency")
            or company.get("company_currency")
            or company.get("currency")
        )
        compatible = (
            row.get("baseline_approved") is True
            and row.get("baseline_kind") == "unadjusted_forecast"
            and _name(row.get("baseline_subject")) == _name(company["company_name"])
            and row.get("baseline_currency") == currency
            and isinstance(native_scale, (float, int))
            and not isinstance(native_scale, bool)
            and native_scale > 0
            and isinstance(scale, (float, int))
            and not isinstance(scale, bool)
            and scale > 0
            and row.get("baseline_scope") == scope
            and bool(scope)
            and row.get("forecast_target_start") == target_start.isoformat()
            and row.get("forecast_target_end") == target_end.isoformat()
        )
        if not compatible:
            row["forecast_lookup_status"] = (
                "candidate_requires_subject_scope_units_period_and_unadjusted_review"
            )
            continue
        row.update(
            baseline_revenue=row["forecast_candidate_baseline_revenue"],
            baseline_source=f"{forecast_relation} | {candidate['source_row_id']}",
            forecast_vintage=candidate.get("forecast_vintage"),
            forecast_vintage_status="current_database_snapshot_not_historical_replay",
            forecast_lookup_status="applied_reviewed_database_baseline",
        )
    return results, audit
