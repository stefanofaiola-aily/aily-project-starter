"""Bounded, schema-discovered reads with separate injected database clients."""

from datetime import UTC, datetime
from typing import Any, Protocol

from .inputs import key
from .models import Inputs, Row, Snapshot, clean, fingerprint, instant, truth


class Reader(Protocol):
    def fetch_data_as_df(
        self, query: str, *, bind_params: tuple[Any, ...] = ...
    ) -> Any: ...


FINANCE_COLUMNS = [
    "symbol",
    "period",
    "calendar_year",
    "date",
    "reported_currency",
    "revenue",
    "cost_of_revenue",
    "gross_profit",
    "ebitda",
    "accepted_date",
    "filling_date",
    "link",
    "final_link",
    "crawled_at",
    "period_start",
    "period_end",
    "scope",
    "unit_multiplier",
    "published_at",
]
POST_COLUMNS = [
    "post_id",
    "profile_id",
    "profile_username",
    "post_url",
    "post_type",
    "photos_number",
    "date_posted",
    "caption",
    "like_count",
    "video_view_count",
    "comment_count",
    "is_paid_partnership",
    "crawled_date",
    "crawled_at",
]
PROFILE_COLUMNS = [
    "profile_id",
    "profile_username",
    "followers_count",
    "followers",
    "follower_count",
    "crawled_date",
    "crawled_at",
]
LIGHT_COLUMNS = [
    "company_code",
    "reported_date",
    "year",
    "quarter",
    "type_filter_code",
    "type_filter_value",
]
SPECS = {
    "light.light_companies": [
        "company_code",
        "company_name",
        "company_label",
        "company_ticker",
        "company_currency",
        "currency",
        "company_context",
        "is_public",
    ],
    "light.light_financial_statements_actuals": LIGHT_COLUMNS,
    "ai.light_financial_statements_forecast": LIGHT_COLUMNS,
    **{
        f"normalized.{name}": FINANCE_COLUMNS
        for name in (
            "v_finance_financial_statements",
            "finance_fmp_financial_statements",
            "finance_interpolated_financial_statements",
            "finance_perplexity_financial_statements",
        )
    },
    "denormalized.finance_financial_statement_overrides": [
        "event_id",
        "company_code",
        "symbol",
        "calendar_year",
        "period",
        "metric",
        "value",
        "reported_currency",
        "action",
        "reason",
        "changed_at",
    ],
    "normalized.social_media_instagram_posts": POST_COLUMNS,
    "normalized.v_social_media_instagram_posts": POST_COLUMNS,
    "normalized.social_media_instagram_profiles": PROFILE_COLUMNS,
    "denormalized.social_media_bright_data_instagram_posts": [
        "post_id",
        "user_posted_id",
        "user_posted",
        "url",
        "content_type",
        "date_posted",
        "description",
        "likes",
        "num_comments",
        "video_view_count",
        "is_paid_partnership",
        "photos_number",
        "crawled_date",
        "crawled_at",
    ],
    "denormalized.social_media_bright_data_instagram_profiles": [
        "id",
        "account",
        "profile_url",
        "profile_name",
        "followers",
        "crawled_date",
        "crawled_at",
    ],
    "normalized.finance_general_competitors": [
        "company_code",
        "competitor_code",
        "competitor_name",
        "competitor_score",
        "is_public",
    ],
}


def verify_read_only(client: Reader) -> None:
    frame = client.fetch_data_as_df(
        "SELECT current_setting('transaction_read_only') AS transaction_read_only, "
        "current_setting('default_transaction_read_only') "
        "AS default_transaction_read_only"
    )
    rows = frame.to_dict("records")
    if len(rows) != 1 or any(
        str(rows[0].get(k)).lower() != "on"
        for k in ("transaction_read_only", "default_transaction_read_only")
    ):
        raise ValueError(
            "Both transaction and default transaction read-only must be on"
        )


def discover(client: Reader, relations: list[str]) -> dict[str, set[str]]:
    schemas = sorted({r.split(".")[0] for r in relations})
    placeholders = ",".join(["%s"] * len(schemas))
    frame = client.fetch_data_as_df(
        "SELECT table_schema, table_name, column_name "
        "FROM information_schema.columns "
        f"WHERE table_schema IN ({placeholders}) "
        "ORDER BY table_schema, table_name, ordinal_position LIMIT %s",
        bind_params=(*schemas, 10001),
    )
    if len(frame) > 10000:
        raise ValueError("Schema discovery exceeded limit")
    result: dict[str, set[str]] = {}
    for row in frame.to_dict("records"):
        result.setdefault(f"{row['table_schema']}.{row['table_name']}", set()).add(
            row["column_name"]
        )
    return result


def candidate_mappings(inputs: Inputs, registry: list[Row]) -> list[Row]:
    """Exact reviewed aliases/codes only; candidates never become approvals."""
    candidates = []
    for entity in inputs.entities:
        names = {key(str(entity["name"]))}
        if entity.get("mapping_approved"):
            names.update(
                key(x.strip())
                for x in str(entity.get("aliases") or "").split(";")
                if x.strip()
            )
        matches = [
            r
            for r in registry
            if (
                entity.get("light_code")
                and r.get("company_code") == entity["light_code"]
            )
            or any(
                key(str(r.get(c) or "")) in names
                for c in ("company_name", "company_label", "company_code")
            )
        ]
        for row in matches:
            candidates.append(
                {
                    "entity_id": entity["entity_id"],
                    **row,
                    "mapping_status": "candidate_requires_review",
                }
            )
    return candidates


def extract(
    light: Reader,
    shared: Reader,
    inputs: Inputs,
    first_year: int,
    last_year: int,
    limit: int = 100000,
    *,
    candidate_symbols: tuple[str, ...] = (),
    candidate_handles: tuple[str, ...] = (),
) -> Snapshot:
    if not 1900 <= first_year <= last_year <= 2100 or not 1 <= limit <= 500000:
        raise ValueError("Use a bounded year interval and row limit")
    verify_read_only(light)
    verify_read_only(shared)
    light_schema = discover(
        light, [r for r in SPECS if r.startswith(("light.", "ai."))]
    )
    shared_schema = discover(
        shared, [r for r in SPECS if not r.startswith(("light.", "ai."))]
    )
    stamp = datetime.now(UTC).isoformat()
    result = Snapshot(
        metadata={
            "extracted_at": stamp,
            "authenticated": True,
            "first_year": first_year,
            "last_year": last_year,
            "queries": [],
            "limitations": [],
            "discovered_columns": {
                relation: sorted(columns)
                for relation, columns in (light_schema | shared_schema).items()
                if relation in SPECS
            },
            "shared_role_warning": (
                "Read-only session does not replace database-enforced grants; "
                "DAL shared secret may use dbo"
            ),
        }
    )

    def read(
        client: Reader,
        schema: dict[str, set[str]],
        relation: str,
        where: str,
        params: tuple[Any, ...],
        required: set[str],
    ) -> list[Row]:
        present = schema.get(relation, set())
        columns = [c for c in SPECS[relation] if c in present]
        if not required.issubset(present):
            result.metadata["limitations"].append(
                f"{relation}: missing relation/required columns "
                f"{sorted(required - present)}"
            )
            return []
        query = f"SELECT {', '.join(columns)} FROM {relation} WHERE {where} LIMIT %s"
        frame = client.fetch_data_as_df(query, bind_params=(*params, limit + 1))
        if len(frame) > limit:
            raise ValueError(f"{relation}: export exceeded row limit; narrow scope")
        rows = clean(frame.to_dict("records"))
        result.metadata["queries"].append(
            {
                "source_relation": relation,
                "columns": columns,
                "query": query,
                "scope": clean(params),
                "row_count": len(rows),
                "extracted_at": stamp,
            }
        )
        return [
            {
                **r,
                "source_relation": relation,
                "source_row_id": fingerprint({"relation": relation, "row": r}),
                "extracted_at": stamp,
            }
            for r in rows
        ]

    result.registry = read(
        light, light_schema, "light.light_companies", "TRUE", (), {"company_code"}
    )
    mappings = candidate_mappings(inputs, result.registry)
    result.metadata["candidate_mappings"] = mappings
    codes = sorted(
        {str(e["light_code"]) for e in inputs.entities if e.get("light_code")}
        | {str(r["company_code"]) for r in mappings}
    )
    symbols = sorted(
        {str(e["shared_symbol"]) for e in inputs.entities if e.get("shared_symbol")}
        | {str(r.get("company_ticker") or r["company_code"]) for r in mappings}
        | set(codes)
    )
    symbols = sorted(
        set(symbols)
        | set(candidate_symbols)
        | {
            alias.strip()
            for entity in inputs.entities
            if truth(entity.get("mapping_approved")) and entity.get("evidence")
            for alias in str(entity.get("aliases") or "").split(";")
            if alias.strip()
        }
    )
    handles = sorted(
        {
            str(e["handle"]).lower().lstrip("@")
            for e in inputs.entities
            if e.get("handle")
        }
        | {h.lower().lstrip("@") for h in candidate_handles}
    )

    def slots(items: list[str]) -> str:
        return ",".join(["%s"] * len(items))

    if codes:
        for relation in (
            "light.light_financial_statements_actuals",
            "ai.light_financial_statements_forecast",
        ):
            rows = read(
                light,
                light_schema,
                relation,
                f"company_code IN ({slots(codes)}) AND year BETWEEN %s AND %s "
                "AND type_filter_code IN "
                "('revenue','cost_of_revenue','gross_profit','ebitda')",
                (*codes, first_year, last_year),
                {"company_code", "year", "type_filter_code", "type_filter_value"},
            )
            for r in rows:
                r.update(
                    metric=r["type_filter_code"],
                    amount=r["type_filter_value"],
                    kind="forecast" if relation.startswith("ai.") else "actual",
                    source_classification="current_snapshot",
                    available_at=None,
                    vintage_verified=False,
                    period_label=f"Light fiscal {r['year']} {r.get('quarter')}",
                )
            result.financials.extend(rows)
    if symbols:
        for relation in (
            r
            for r in SPECS
            if r.startswith("normalized.") and "financial_statements" in r
        ):
            rows = read(
                shared,
                shared_schema,
                relation,
                f"symbol IN ({slots(symbols)}) AND calendar_year BETWEEN %s AND %s",
                (*symbols, first_year, last_year),
                {"symbol", "calendar_year", "revenue"},
            )
            classification = (
                "reported"
                if "fmp" in relation
                else "interpolated"
                if "interpolated" in relation
                else "estimated"
                if "perplexity" in relation
                else "consolidated_requires_source_review"
            )
            for r in rows:
                for metric in ("revenue", "cost_of_revenue", "gross_profit", "ebitda"):
                    if r.get(metric) is None:
                        continue
                    # Consolidated metadata is not revenue-level vintage proof.
                    captures = [
                        t
                        for col in ("accepted_date", "crawled_at")
                        if (t := instant(r.get(col))) is not None
                    ]
                    result.financials.append(
                        {
                            **r,
                            "source_row_id": fingerprint(
                                {"row": r["source_row_id"], "metric": metric}
                            ),
                            "metric": metric,
                            "amount": r[metric],
                            "currency": r.get("reported_currency"),
                            "kind": "actual",
                            "source_classification": classification,
                            "period_label": (
                                f"Shared calendar {r['calendar_year']} "
                                f"{r.get('period')}"
                            ),
                            "available_at": max(captures).isoformat()
                            if captures
                            else None,
                            "vintage_verified": False,
                        }
                    )
        override_scope = f"symbol IN ({slots(symbols)})"
        if codes:
            override_scope += f" OR company_code IN ({slots(codes)})"
        result.overrides = read(
            shared,
            shared_schema,
            "denormalized.finance_financial_statement_overrides",
            f"({override_scope}) AND calendar_year BETWEEN %s AND %s",
            (*symbols, *codes, first_year, last_year),
            {"symbol", "calendar_year", "metric", "changed_at"},
        )
        source_index: dict[tuple[Any, ...], list[Row]] = {}
        aliases: dict[str, set[str]] = {}
        for company in result.registry:
            symbol = str(company.get("company_ticker") or company["company_code"])
            aliases.setdefault(symbol, set()).add(str(company["company_code"]))
        for row in result.financials:
            ident = tuple(
                row.get(k) for k in ("symbol", "calendar_year", "period", "metric")
            )
            source_index.setdefault(ident, []).append(row)
        for row in result.financials:
            events = [
                e
                for e in result.overrides
                if (
                    row.get("symbol")
                    and e.get("symbol") == row.get("symbol")
                    or not e.get("symbol")
                    and str(e.get("company_code"))
                    in aliases.get(str(row.get("symbol")), set())
                )
                and e.get("calendar_year") == row.get("calendar_year")
                and e.get("period") == row.get("period")
                and e.get("metric") == row.get("metric")
            ]
            row["correction_events"] = events
            if row["source_classification"] == "consolidated_requires_source_review":
                ident = tuple(
                    row.get(k) for k in ("symbol", "calendar_year", "period", "metric")
                )
                candidates = [
                    r
                    for r in source_index[ident]
                    if r.get("source_relation") != row.get("source_relation")
                ]
                row["source_candidates"] = [
                    {
                        k: r.get(k)
                        for k in (
                            "source_row_id",
                            "source_relation",
                            "amount",
                            "currency",
                            "source_classification",
                            "available_at",
                        )
                    }
                    for r in candidates
                ]
                if events:
                    exact = [e for e in events if e.get("symbol") == row.get("symbol")]
                    latest = max(
                        exact or events,
                        key=lambda e: (
                            str(e.get("changed_at") or ""),
                            str(e.get("event_id") or ""),
                        ),
                    )
                    if (
                        latest.get("action") == "set"
                        and row.get("currency")
                        and latest.get("reported_currency") == row.get("currency")
                    ):
                        row["source_classification"] = (
                            "corrected_requires_vintage_review"
                        )
                        change_time = instant(latest.get("changed_at"))
                        native_time = instant(row.get("available_at"))
                        row["available_at"] = (
                            max(change_time, native_time).isoformat()
                            if change_time and native_time
                            else None
                        )
    if handles:
        relation = (
            "normalized.v_social_media_instagram_posts"
            if {"crawled_at", "post_id", "profile_username", "date_posted"}.issubset(
                shared_schema.get("normalized.v_social_media_instagram_posts", set())
            )
            else "normalized.social_media_instagram_posts"
        )
        result.posts = read(
            shared,
            shared_schema,
            relation,
            f"LOWER(profile_username) IN ({slots(handles)}) "
            "AND date_posted >= %s AND date_posted < %s",
            (*handles, f"{first_year}-01-01", f"{last_year + 1}-01-01"),
            {"profile_username", "date_posted", "post_id", "crawled_at"},
        )
        result.profiles = read(
            shared,
            shared_schema,
            "normalized.social_media_instagram_profiles",
            f"LOWER(profile_username) IN ({slots(handles)}) "
            "AND crawled_date >= %s AND crawled_date < %s",
            (*handles, f"{first_year}-01-01", f"{last_year + 1}-01-01"),
            {"profile_username", "crawled_date"},
        )
        for row in result.profiles:
            values = [
                row[c]
                for c in ("followers_count", "followers", "follower_count")
                if row.get(c) is not None
            ]
            row["followers_count"] = values[0] if len(set(values)) == 1 else None
        # Never merge mirror observations for the same handle. Use the raw
        # report-referenced archive only for accounts absent from normalization.
        present_handles = {str(r["profile_username"]).lower() for r in result.posts}
        missing = [h for h in handles if h not in present_handles]
        if missing:
            fallback = read(
                shared,
                shared_schema,
                "denormalized.social_media_bright_data_instagram_posts",
                f"LOWER(user_posted) IN ({slots(missing)}) "
                "AND date_posted >= %s AND date_posted < %s",
                (*missing, f"{first_year}-01-01", f"{last_year + 1}-01-01"),
                {"user_posted", "post_id", "date_posted", "crawled_at"},
            )
            for row in fallback:
                row.update(
                    profile_username=row.get("user_posted"),
                    profile_id=row.get("user_posted_id"),
                    post_url=row.get("url"),
                    caption=row.get("description"),
                    post_type=row.get("content_type"),
                    like_count=row.get("likes"),
                    comment_count=row.get("num_comments"),
                )
            result.posts.extend(fallback)
        profile_handles = {str(r["profile_username"]).lower() for r in result.profiles}
        missing_profiles = [h for h in handles if h not in profile_handles]
        if missing_profiles:
            fallback_profiles = read(
                shared,
                shared_schema,
                "denormalized.social_media_bright_data_instagram_profiles",
                f"LOWER(account) IN ({slots(missing_profiles)}) "
                "AND crawled_date >= %s AND crawled_date < %s",
                (*missing_profiles, f"{first_year}-01-01", f"{last_year + 1}-01-01"),
                {"account", "crawled_date"},
            )
            for row in fallback_profiles:
                row.update(
                    profile_username=row.get("account"),
                    profile_id=row.get("id"),
                    followers_count=row.get("followers"),
                )
            result.profiles.extend(fallback_profiles)
    if codes:
        result.metadata["competitor_candidates"] = read(
            shared,
            shared_schema,
            "normalized.finance_general_competitors",
            f"company_code IN ({slots(codes)})",
            tuple(codes),
            {"company_code", "competitor_code"},
        )
    result.metadata["limitations"].extend(
        [
            "Financial values require verified source/vintage evidence before "
            "eligibility; consolidated metadata cannot prove a revenue vintage.",
            "Light forecasts have no native vintage in the inspected relation. "
            "A dated authenticated forecast export is required for strict replay.",
        ]
    )
    return result
