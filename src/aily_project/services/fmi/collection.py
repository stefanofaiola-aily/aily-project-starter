"""Collect source candidates independently of score-release approval gates."""

from datetime import UTC, datetime
from pathlib import Path
from statistics import median

from .extraction import SPECS, Reader, discover, verify_read_only
from .handover import (
    candidate_symbols,
    matched_reports,
    prepare_candidates,
    read_reports,
)
from .models import (
    Inputs,
    Row,
    Snapshot,
    calendar_date,
    clean,
    fingerprint,
    instant,
    number,
    truth,
)

SOCIAL_RELATIONS = (
    "normalized.social_media_instagram_profiles",
    "normalized.v_social_media_instagram_profiles",
    "normalized.social_media_instagram_posts",
    "denormalized.social_media_bright_data_instagram_posts",
    "denormalized.social_media_bright_data_instagram_profiles",
)


def inventory(
    light: Reader,
    shared: Reader,
    first_year: int,
    last_year: int,
    inputs: Inputs | None = None,
) -> Row:
    """Discover actual account identifiers, including report-referenced archives."""
    if not 1900 <= first_year <= last_year <= 2100:
        raise ValueError("Use a bounded year interval")
    verify_read_only(light)
    verify_read_only(shared)
    light_schema = discover(light, ["light.light_companies"])
    finance_relations = [
        r for r in SPECS if r.startswith("normalized.") and "financial_statements" in r
    ]
    schema = discover(shared, list(SOCIAL_RELATIONS) + finance_relations)
    stamp = datetime.now(UTC).isoformat()
    result: Row = {
        "authenticated": True,
        "extracted_at": stamp,
        "social_columns": {r: sorted(schema.get(r, [])) for r in SOCIAL_RELATIONS},
        "accounts": [],
        "registry": [],
        "queries": [],
        "financial_symbols": [],
    }
    columns = [
        c
        for c in (
            "company_code",
            "company_name",
            "company_label",
            "company_ticker",
            "currency",
            "is_public",
            "company_context",
        )
        if c in light_schema.get("light.light_companies", set())
    ]
    if "company_code" not in columns:
        raise ValueError("Light company registry is unavailable")
    query = f"SELECT {', '.join(columns)} FROM light.light_companies LIMIT %s"
    frame = light.fetch_data_as_df(query, bind_params=(10001,))
    if len(frame) > 10000:
        raise ValueError("Company inventory exceeded limit")
    result["registry"] = clean(frame.to_dict("records"))
    result["queries"].append(
        {"query": query, "scope": [10001], "row_count": len(frame)}
    )
    for relation in SOCIAL_RELATIONS:
        present = schema.get(relation, set())
        username = next(
            (
                c
                for c in ("profile_username", "username", "user_posted", "account")
                if c in present
            ),
            None,
        )
        if not username:
            continue
        selected = [username]
        profile_id = next(
            (c for c in ("profile_id", "user_posted_id", "id") if c in present), None
        )
        if profile_id:
            selected.append(profile_id)
        date = next(
            (c for c in ("date_posted", "crawled_date", "crawled_at") if c in present),
            None,
        )
        if date is None:
            continue
        query = (
            f"SELECT DISTINCT {', '.join(selected)} FROM {relation} "
            f"WHERE {date} >= %s AND {date} < %s LIMIT %s"
        )
        params = (f"{first_year}-01-01", f"{last_year + 1}-01-01", 10001)
        frame = shared.fetch_data_as_df(query, bind_params=params)
        if len(frame) > 10000:
            raise ValueError("Account inventory exceeded limit")
        result["queries"].append(
            {"query": query, "scope": list(params), "row_count": len(frame)}
        )
        for row in clean(frame.to_dict("records")):
            result["accounts"].append(
                {
                    "profile_username": row[username],
                    "profile_id": row.get(profile_id) if profile_id else None,
                    "source_relation": relation,
                    "source_row_id": fingerprint({"relation": relation, "row": row}),
                }
            )
    probes = {
        str(r[c])
        for r in result["registry"]
        for c in ("company_code", "company_ticker")
        if r.get(c)
    }
    if inputs:
        probes.update(s for e in inputs.entities for s in candidate_symbols(e))
    result["financial_symbol_search_scope"] = sorted(probes)
    for relation in finance_relations:
        if not {"symbol", "calendar_year"}.issubset(schema.get(relation, set())):
            continue
        slots = ",".join("%s" for _ in probes)
        query = (
            f"SELECT DISTINCT symbol FROM {relation} "
            f"WHERE symbol IN ({slots}) AND calendar_year BETWEEN %s AND %s LIMIT %s"
        )
        params = (*sorted(probes), first_year, last_year, 10001)
        frame = shared.fetch_data_as_df(query, bind_params=params)
        if len(frame) > 10000:
            raise ValueError("Financial symbol inventory exceeded limit")
        result["queries"].append(
            {"query": query, "scope": list(params), "row_count": len(frame)}
        )
        result["financial_symbols"].extend(
            {"symbol": r["symbol"], "source_relation": relation}
            for r in frame.to_dict("records")
        )
    return result


def collected_inputs(
    inputs: Inputs, data: Row, handover: Path
) -> tuple[Inputs, list[Row], list[Row]]:
    reports = read_reports(handover)
    proposed, audit = prepare_candidates(inputs, data, reports)
    for analysis in proposed.analyses:
        if truth(analysis.get("reviewed")) or analysis.get("route"):
            continue
        entity = next(
            e for e in proposed.entities if e["entity_id"] == analysis["entity_id"]
        )
        refs = matched_reports(entity, reports)
        shows = [s for r in refs for s in r["shows"]]
        historical = [s for s in shows if s["show_date"].startswith("2025-")]
        zones = {z for r in refs for z in r["timezones"]}
        if historical and len(zones) == 1:
            selected = max(historical, key=lambda s: s["show_date"])
            analysis.update(
                route="show",
                collection=selected["collection"],
                show_date=selected["show_date"],
                timezone=zones.pop(),
                evidence=selected["evidence"] + "; proposed analysis, not approved",
            )
    return proposed, reports, audit


def financial_candidates(entity: Row, snapshot: Snapshot) -> list[Row]:
    symbols = candidate_symbols(entity)
    return [
        r
        for r in snapshot.financials
        if (
            entity.get("light_code")
            and r.get("company_code") == entity["light_code"]
            or str(r.get("symbol") or "") in symbols
        )
    ]


def collection_payload(
    inputs: Inputs, snapshot: Snapshot, audit: list[Row], reports: list[Row]
) -> Row:
    """Source measurements are inspectable even when historical FMI is gated."""
    coverage, financial, social, facts = [], [], [], []
    for entity in inputs.entities:
        is_prospect = truth(entity.get("prospect"))
        ident = entity["entity_id"]
        rows = financial_candidates(entity, snapshot)
        revenues = [r for r in rows if r["metric"] == "revenue"]
        posts = [
            r
            for r in snapshot.posts
            if str(r.get("profile_username", "")).lower()
            == str(entity.get("handle") or "").lower()
        ]
        # Current descriptive snapshots are separate from strict historical replay.
        # Preserve latest captures without filling unknown timing or missing likes.
        retained: dict[str, Row] = {}
        for p in posts:
            post = str(p.get("post_id") or p.get("post_url") or "")
            if not post:
                continue
            old = retained.get(post)
            capture, old_capture = (
                instant(p.get("crawled_at")),
                instant(old.get("crawled_at")) if old else None,
            )
            if (
                old is None
                or capture is not None
                and (old_capture is None or capture > old_capture)
            ):
                retained[post] = p
        index = next(a for a in audit if a["entity_id"] == ident)
        actual = [r for r in revenues if r["kind"] == "actual"]
        forecast = [r for r in revenues if r["kind"] == "forecast"]
        reasons = []
        if not revenues:
            reasons.append(
                "No revenue rows for candidate codes/symbols in queried databases"
            )
        if not posts:
            reasons.append(
                "No own-account Instagram posts for proposed handle in queried archives"
            )
        if revenues:
            reasons.append(
                "Select comparable periods and verify reporting scope, "
                "units and source vintage"
            )
        if posts:
            reasons.append(
                "Review account scope, comparable windows and collection relevance"
            )
        coverage.append(
            {
                "brand_id": ident,
                "name": entity["name"],
                "light_code": entity.get("light_code"),
                "ticker": entity.get("ticker"),
                "shared_symbol": entity.get("shared_symbol"),
                "financial_subject": entity.get("financial_subject"),
                "proxy": truth(entity["proxy"])
                if entity.get("proxy") is not None
                else None,
                "proxy_label": entity.get("proxy_label"),
                "observed_shared_symbols": sorted(
                    {r["symbol"] for r in revenues if r.get("symbol")}
                ),
                "handle": entity.get("handle"),
                "report_count": index["report_count"],
                "actual_revenue_rows": len(actual),
                "forecast_revenue_rows": len(forecast),
                "financial_metrics_rows": len(rows),
                "social_capture_rows": len(posts),
                "distinct_posts": len(retained),
                "usable_likes_posts": sum(
                    (likes := number(p.get("like_count"))) is not None and likes >= 0
                    for p in retained.values()
                ),
                "identity_status": index["identity_status"],
                "revenue_collection_status": "collected_candidates"
                if revenues
                else "no_matching_rows",
                "social_collection_status": "collected_candidates"
                if posts
                else "no_matching_rows",
                "score_release_status": "review_required",
                "next_steps": "; ".join(reasons),
                "source_relations": sorted(
                    {r["source_relation"] for r in rows + posts}
                ),
                "report_evidence": index["report_paths"],
            }
        )
        if not is_prospect:
            coverage.pop()  # Headline coverage stays one row per prospect.
        for r in rows:
            financial.append(
                {
                    "brand_id": ident,
                    "name": entity["name"],
                    "prospect": is_prospect,
                    **{
                        k: r.get(k)
                        for k in (
                            "company_code",
                            "symbol",
                            "metric",
                            "amount",
                            "kind",
                            "currency",
                            "year",
                            "quarter",
                            "calendar_year",
                            "period",
                            "date",
                            "reported_date",
                            "period_label",
                            "period_start",
                            "period_end",
                            "scope",
                            "unit_multiplier",
                            "source_classification",
                            "available_at",
                            "vintage_verified",
                            "source_relation",
                            "source_row_id",
                            "extracted_at",
                            "accepted_date",
                            "filling_date",
                            "crawled_at",
                            "link",
                            "final_link",
                        )
                    },
                    "correction_count": len(r.get("correction_events", [])),
                    "source_candidate_count": len(r.get("source_candidates", [])),
                    "eligibility": "source_candidate_not_released_metric",
                }
            )
        for year in range(
            snapshot.metadata["first_year"], snapshot.metadata["last_year"] + 1
        ):
            year_posts = []
            for p in retained.values():
                try:
                    posted = calendar_date(p.get("date_posted"))
                except (ValueError, TypeError):
                    continue
                if posted.year == year:
                    year_posts.append(p)
            if not year_posts:
                continue
            record: Row = {
                "brand_id": ident,
                "name": entity["name"],
                "handle": entity.get("handle"),
                "prospect": is_prospect,
                "year": year,
                "total_posts": len(year_posts),
                "measurement_basis": (
                    "current descriptive captures; not historical replay"
                ),
                "unknown_capture_posts": sum(
                    instant(p.get("crawled_at")) is None for p in year_posts
                ),
            }
            for metric in ("like_count", "comment_count", "video_view_count"):
                values = [
                    v
                    for p in year_posts
                    if (v := number(p.get(metric))) is not None and v >= 0
                ]
                record[f"usable_{metric}"] = len(values)
                record[f"median_{metric}"] = median(values) if values else None
            record["common_months"] = sorted(
                {calendar_date(p["date_posted"]).month for p in year_posts}
            )
            record["first_post_date"] = min(
                calendar_date(p["date_posted"]) for p in year_posts
            )
            record["last_post_date"] = max(
                calendar_date(p["date_posted"]) for p in year_posts
            )
            record["source_relations"] = sorted(
                {p["source_relation"] for p in year_posts}
            )
            social.append(record)
        for report in matched_reports(entity, reports):
            for show in report["shows"]:
                facts.append(
                    {
                        "brand_id": ident,
                        "name": entity["name"],
                        "kind": "show_date",
                        "collection": show["collection"],
                        "show_date": show["show_date"],
                        "reference": report["path"],
                        "details": (
                            "Report evidence; analysis selection/relevance "
                            "not yet approved"
                        ),
                    }
                )
            facts.append(
                {
                    "brand_id": ident,
                    "name": entity["name"],
                    "kind": "report_scope",
                    "reference": report["path"],
                    "details": (
                        " ".join(report["scope_evidence"])[:600]
                        + (
                            " (Full scope in source report.)"
                            if report["scope_evidence"]
                            else "Scope requires source review."
                        )
                    ),
                }
            )
    metadata = [
        {
            "kind": "collection",
            "details": (
                "Database source candidates. Descriptive social snapshots are "
                "not strict historical replay. No source amounts were copied "
                "from reports. No current forecasts substituted for "
                "historical vintages."
            ),
        },
        {
            "kind": "extraction",
            "extracted_at": snapshot.metadata["extracted_at"],
            "details": "Authenticated database collection",
        },
    ]
    metadata.extend(
        {
            "kind": "query",
            "reference": q["source_relation"],
            "row_count": q["row_count"],
            "details": q["query"],
            "query_scope": q["scope"],
        }
        for q in snapshot.metadata["queries"]
    )

    def sheet(name: str, rows: list[Row]) -> Row:
        keys = list(dict.fromkeys(k for r in rows for k in r)) or ["brand_id", "status"]
        fields = []
        for k in keys:
            type_, unit = "string", "text"
            if k in {
                "date",
                "reported_date",
                "period_start",
                "period_end",
                "show_date",
                "first_post_date",
                "last_post_date",
            }:
                type_, unit = "date", "calendar_date"
            elif k in {
                "available_at",
                "extracted_at",
                "accepted_date",
                "filling_date",
                "crawled_at",
            }:
                type_, unit = "datetime", "source_timestamp"
            elif k == "amount" or k.startswith("median_"):
                type_, unit = "number", "source_units" if k == "amount" else "count"
            elif k.endswith(("_rows", "_count", "_posts")) or k.startswith("usable_"):
                type_, unit = "integer", "count"
            fields.append({"field_key": k, "type": type_, "unit": unit})
        return {
            "name": name,
            "keys": keys,
            "labels": [k.replace("_", " ").capitalize() for k in keys],
            "rows": clean(rows),
            "fields": fields,
        }

    return {
        "kind": "collection",
        "sheets": [
            sheet("Collection coverage", coverage),
            sheet("Revenue candidates", financial),
            sheet("Social annual snapshots", social),
            sheet("Report facts", facts),
            sheet("Collection evidence", metadata),
        ],
    }
