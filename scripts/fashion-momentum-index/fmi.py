"""One-off FMI calculations and small read-only CSV exports. No cloud setup here."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import timedelta
from typing import Any

import pandas as pd

FINANCIAL_COLUMNS = [
    "entity",
    "company_id",
    "company_name",
    "period_start",
    "period_end",
    "period_type",
    "metric",
    "scope",
    "currency",
    "amount",
    "unit_multiplier",
    "classification",
    "published_at",
    "version",
    "source",
    "source_locator",
]
SOCIAL_COLUMNS = [
    "handle",
    "post_key",
    "date_posted",
    "likes",
    "crawled_at",
    "url",
    "description",
]


def yes(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def clip_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def band(score: float) -> str:
    # Classify the original float, not its rounded display value.
    if not math.isfinite(score) or not 0 <= score <= 100:
        return "Unavailable"
    return (
        "High"
        if score >= 70
        else "Medium"
        if score >= 60
        else ("Neutral" if score >= 40 else "Low")
    )


def trend_score(latest: float, earlier: float) -> tuple[float, str]:
    change = latest - earlier
    # Avoid floating-point noise changing the document's exact +/-2 pp boundaries.
    if change > 2 and not math.isclose(change, 2, abs_tol=1e-9):
        return 70.0, "Up and coming"
    if change < -2 and not math.isclose(change, -2, abs_tol=1e-9):
        return 30.0, "Fallback / weakening"
    if latest >= 5 - 1e-9 and earlier >= 5 - 1e-9:
        return 80.0, "Strong / sustained outperformance"
    return 50.0, "Neutral / no clear change"


def sales_scenario(score: float, baseline: float, last_year: float) -> dict[str, float]:
    if not math.isfinite(score) or not 0 <= score <= 100:
        return {}
    if not math.isfinite(baseline) or baseline <= 0:
        return {}
    uplift = 0.0 if score <= 60 else 0.03 + (score - 60) / 10 * 0.02
    adjusted = baseline * (1 + uplift)
    return {
        "baseline": baseline,
        "uplift_pct": uplift * 100,
        "adjusted_forecast": adjusted,
        "absolute_adjustment": adjusted - baseline,
        "forecast_yoy_pct": (adjusted / last_year - 1) * 100
        if math.isfinite(last_year) and last_year > 0
        else math.nan,
    }


def quote_identifier(name: str) -> str:
    # Only schema-discovered identifiers; values always use DB-API bind parameters.
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return '"' + name + '"'


def require_read_only(db: Any) -> None:
    row = db.execute_and_fetch(
        "SELECT current_setting('transaction_read_only') AS read_only"
    )[0]
    if row["read_only"] != "on":
        raise RuntimeError("Refusing queries on a writable database session.")


def discover_columns(db: Any, tables: list[tuple[str, str]]) -> pd.DataFrame:
    require_read_only(db)
    rows: list[dict[str, Any]] = []
    for schema, table in tables:
        rows.extend(
            db.execute_and_fetch(
                "SELECT table_schema, table_name, column_name, "
                "data_type, ordinal_position "
                "FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = %s "
                "ORDER BY ordinal_position LIMIT 200",
                bind_params=(schema, table),
            )
        )
    return pd.DataFrame(
        rows,
        columns=pd.Index(
            [
                "table_schema",
                "table_name",
                "column_name",
                "data_type",
                "ordinal_position",
            ]
        ),
    )


def export_light_revenue(
    db: Any,
    source: str,
    company_ids: dict[str, str],
    first_year: int,
    last_year: int,
    limit: int = 10000,
) -> pd.DataFrame:
    """Download confirmed Light revenue columns; retain unknown metadata as missing."""
    sources = {
        "actuals": ("light", "light_financial_statements_actuals", "Actual"),
        "forecasts": ("ai", "light_financial_statements_forecast", "Forecast"),
    }
    if source not in sources:
        raise ValueError("Choose actuals or forecasts.")
    if not company_ids or not all(str(v).strip() for v in company_ids.values()):
        raise ValueError("Set nonempty company codes.")
    if len(set(company_ids.values())) != len(company_ids):
        raise ValueError("Each financial entity needs a distinct company code.")
    if not 1 <= first_year <= last_year <= 9999 or limit < 1:
        raise ValueError("Use valid, bounded fiscal years and a positive row limit.")
    require_read_only(db)
    schema, table, classification = sources[source]
    native_columns = [
        "company_code",
        "reported_date",
        "year",
        "quarter",
        "type_filter_code",
        "type_filter_value",
    ]
    discovered = discover_columns(db, [(schema, table)])["column_name"].tolist()
    if set(native_columns) - set(discovered):
        raise ValueError("Light source schema differs from the verified six columns.")
    codes = list(company_ids.values())
    slots = ", ".join(["%s"] * len(codes))
    rows = db.execute_and_fetch(
        "SELECT company_code, reported_date, year, quarter, "
        "type_filter_code, type_filter_value "
        f"FROM {quote_identifier(schema)}.{quote_identifier(table)} "
        f"WHERE company_code IN ({slots}) "
        "AND type_filter_code = %s AND year BETWEEN %s AND %s "
        "ORDER BY company_code, year, quarter, reported_date LIMIT %s",
        bind_params=(*codes, "revenue", first_year, last_year, limit + 1),
    )
    if len(rows) > limit:
        raise ValueError("Light export exceeds row limit; narrow companies or years.")
    frame = pd.DataFrame(rows, columns=pd.Index(native_columns))
    reverse_ids = {value: entity for entity, value in company_ids.items()}
    frame["entity"] = frame["company_code"].map(reverse_ids)
    frame["company_id"] = frame["company_code"]
    frame["metric"] = frame["type_filter_code"]
    frame["amount"] = frame["type_filter_value"]
    frame["period_type"] = "quarter"
    frame["classification"] = classification
    frame["source"] = f"{schema}.{table}"
    frame["source_locator"] = (
        "Light current snapshot; native fiscal year/quarter/reported_date retained"
    )
    # Light does not expose these in either source table. No inferred currency,
    # units, reporting scope, fiscal boundaries or forecast publication version.
    for column in FINANCIAL_COLUMNS:
        if column not in frame:
            frame[column] = pd.NA
    return add_row_ids(frame[FINANCIAL_COLUMNS + native_columns])


def add_row_ids(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["source_row_id"] = [
        hashlib.sha256(
            json.dumps(
                row,
                sort_keys=True,
                default=str,
                allow_nan=True,
            ).encode()
        ).hexdigest()[:20]
        for row in frame.to_dict("records")
    ]
    return frame.drop_duplicates("source_row_id")


def export_social(
    db: Any,
    handles: list[str],
    start: str,
    end: str,
    as_of: str,
    limit: int = 25000,
) -> pd.DataFrame:
    """Latest capture per post by cutoff, with one extra day at timezone edges."""
    require_read_only(db)
    if not handles or not start or not end or start > end:
        raise ValueError("Set handles and a bounded social extraction range.")
    cols = discover_columns(
        db,
        [
            ("denormalized", "social_media_bright_data_instagram_posts"),
        ],
    )["column_name"].tolist()
    if set(
        [
            "user_posted",
            "post_id",
            "shortcode",
            "url",
            "date_posted",
            "likes",
            "crawled_at",
        ]
    ) - set(cols):
        raise ValueError(
            "Shared table/columns differ from handover; confirm connection."
        )
    cutoff = pd.Timestamp(as_of)
    if cutoff.tzinfo is None:
        raise ValueError("Use an explicit timezone in as_of, e.g. ...T23:59:59Z.")
    cutoff_day = cutoff.tz_convert("UTC").date().isoformat()
    start_edge = (pd.Timestamp(start).date() - timedelta(days=1)).isoformat()
    end_edge = (pd.Timestamp(end).date() + timedelta(days=1)).isoformat()
    slots = ", ".join(["%s"] * len(handles))
    caption = "description" if "description" in cols else "NULL::text"
    query = f"""
    SELECT lower(user_posted) AS handle,
           coalesce(nullif(post_id, ''), nullif(shortcode, ''), nullif(url, ''))
               AS post_key,
           date_posted,
           CASE WHEN likes >= 0 AND likes < 'Infinity'::float8
                THEN likes ELSE NULL END AS likes,
           crawled_at, url, {caption} AS description
    FROM denormalized.social_media_bright_data_instagram_posts
    WHERE lower(user_posted) IN ({slots})
      AND left(date_posted, 10) BETWEEN %s AND %s
      AND (crawled_at IS NULL OR left(crawled_at, 10) <= %s)
      AND coalesce(nullif(post_id, ''), nullif(shortcode, ''), nullif(url, ''))
          IS NOT NULL
    ORDER BY date_posted, post_key, crawled_at DESC NULLS LAST
    LIMIT %s
    """
    rows = db.execute_and_fetch(
        query,
        bind_params=(
            *[h.lower() for h in handles],
            start_edge,
            end_edge,
            cutoff_day,
            limit + 1,
        ),
    )
    if len(rows) > limit:
        raise ValueError("Social export exceeds row limit; narrow handles/date range.")
    frame = pd.DataFrame(rows, columns=pd.Index(SOCIAL_COLUMNS))
    # Filter exact cutoff BEFORE selecting latest, unlike day-level DISTINCT ON.
    # A later same-day capture must not hide an earlier valid observation.
    frame["_captured"] = pd.to_datetime(
        frame["crawled_at"],
        utc=True,
        errors="coerce",
        format="mixed",
    )
    frame = frame.loc[frame["_captured"].isna() | frame["_captured"].le(cutoff)]
    frame = frame.sort_values(
        ["_captured", "likes"],
        ascending=[False, False],
        na_position="last",
    ).drop_duplicates(["handle", "post_key"])
    return frame[SOCIAL_COLUMNS].sort_values(["date_posted", "post_key"])


def select_financials(
    raw: pd.DataFrame,
    selections: pd.DataFrame,
    annotations: pd.DataFrame,
) -> pd.DataFrame:
    """Choose individual actual/forecast rows explicitly, never sum versions."""
    needed = ["entity", "period_role", "source_row_id"]
    chosen = selections[needed].fillna("")
    chosen = chosen.loc[chosen["source_row_id"].str.strip().ne("")]
    if chosen.duplicated(["entity", "period_role"]).any():
        raise ValueError("Select one financial row per entity and period role.")
    if raw["source_row_id"].duplicated().any():
        raise ValueError("Duplicate financial row IDs; review exports/external inputs.")
    merged = chosen.merge(
        raw,
        on=["entity", "source_row_id"],
        how="left",
        validate="many_to_one",
        indicator=True,
    )
    if merged["_merge"].ne("both").any():
        raise ValueError("A selected financial row ID was not found in this export.")
    merged = merged.drop(columns="_merge")
    # Scope and unit corrections are an explicit, row-specific manual review.
    if not annotations.empty:
        if annotations["source_row_id"].duplicated().any():
            raise ValueError("One scope/unit annotation is allowed per source row.")
        indexed = annotations.set_index("source_row_id")
        reviewable = (
            "company_name",
            "scope",
            "currency",
            "unit_multiplier",
            "period_start",
            "period_end",
            "period_type",
            "published_at",
            "version",
            "source_locator",
        )
        for column in reviewable:
            if column not in indexed:
                continue
            corrections = merged["source_row_id"].map(indexed[column])
            merged[column] = corrections.where(
                corrections.notna() & corrections.astype(str).str.strip().ne(""),
                merged[column],
            )
    return merged


def _financial_row(
    financials: pd.DataFrame,
    entity: str,
    role: str,
    as_of: pd.Timestamp,
    point_in_time: bool,
) -> dict[str, Any]:
    rows = financials.loc[
        financials["entity"].eq(entity) & financials["period_role"].eq(role)
    ]
    if len(rows) != 1:
        raise ValueError(f"{entity}/{role}: select exactly one financial row")
    row = rows.iloc[0].to_dict()
    classification = "Forecast" if role == "target" else "Actual"
    if row["classification"] != classification:
        raise ValueError(f"{entity}/{role}: must be {classification}")
    for column in ("metric", "scope", "currency", "source", "source_locator"):
        if pd.isna(row[column]) or not str(row[column]).strip():
            raise ValueError(f"{entity}/{role}: missing {column}")
    start, end = pd.Timestamp(row["period_start"]), pd.Timestamp(row["period_end"])
    if pd.isna(start) or pd.isna(end) or start > end:
        raise ValueError(f"{entity}/{role}: invalid reporting dates")
    if classification == "Actual" and end.date() > as_of.date():
        raise ValueError(f"{entity}/{role}: actual period ends after cutoff")
    published = pd.to_datetime(row["published_at"], utc=True, errors="coerce")
    if point_in_time and pd.isna(published):
        raise ValueError(f"{entity}/{role}: publication/version date unknown")
    if pd.notna(published) and published > as_of:
        raise ValueError(f"{entity}/{role}: published after cutoff")
    amount, units = float(row["amount"]), float(row["unit_multiplier"])
    if (
        not math.isfinite(amount)
        or not math.isfinite(units)
        or amount < 0
        or units <= 0
    ):
        raise ValueError(
            f"{entity}/{role}: amount must be nonnegative and unit multiplier positive"
        )
    row["value"] = amount * units
    return row


def commercial_components(
    financials: pd.DataFrame,
    analysis: dict[str, Any],
) -> dict[str, Any]:
    entity = analysis["financial_entity"]
    peers = _comparison_peers(analysis)
    if not yes(analysis["comparability_reviewed"]):
        raise ValueError("Review peer periods, financial definitions and scopes first.")
    cutoff = pd.Timestamp(analysis["as_of"])
    series: dict[str, list[dict[str, Any]]] = {}
    for member in [entity, *peers]:
        series[member] = [
            _financial_row(
                financials, member, role, cutoff, yes(analysis["point_in_time"])
            )
            for role in ("oldest", "earlier", "latest")
        ]
        rows = series[member]
        if rows[0]["value"] <= 0 or rows[1]["value"] <= 0:
            raise ValueError(f"{member}: revenue growth denominator is zero")
        for col in ("metric", "scope", "currency", "period_type"):
            if len({r[col] for r in rows}) != 1:
                raise ValueError(f"{member}: inconsistent {col} across periods")
        if analysis["route"] == "fiscal_year" and rows[0]["period_type"] != "annual":
            raise ValueError(f"{member}: fiscal-year route needs annual actuals")
        for previous, current in zip(rows, rows[1:], strict=False):
            delta = (
                pd.Timestamp(current["period_end"])
                - pd.Timestamp(previous["period_end"])
            ).days
            duration_delta = abs(
                (
                    pd.Timestamp(current["period_end"])
                    - pd.Timestamp(current["period_start"])
                ).days
                - (
                    pd.Timestamp(previous["period_end"])
                    - pd.Timestamp(previous["period_start"])
                ).days
            )
            if not 330 <= delta <= 400 or duration_delta > 14:
                raise ValueError(
                    f"{member}: periods are not equivalent prior-year periods"
                )
    if len({series[m][0]["metric"] for m in series}) != 1:
        raise ValueError("Peers must use the same financial metric definition.")
    return revenue_components(
        {member: [row["value"] for row in rows] for member, rows in series.items()},
        entity,
        peers,
    )


def social_component(
    posts: pd.DataFrame,
    labels: pd.DataFrame,
    analysis: dict[str, Any],
    require_review: bool = True,
) -> dict[str, Any]:
    # Only the explicitly provisional notebook may bypass manual attestation.
    if require_review and not yes(analysis["coverage_reviewed"]):
        raise ValueError(
            "Review social coverage, post ages and collection labels first."
        )
    cutoff = pd.Timestamp(analysis["as_of"])
    zone = analysis["timezone"]
    data = posts.loc[posts["handle"].str.lower().eq(analysis["handle"].lower())].copy()
    data["published"] = pd.to_datetime(
        data["date_posted"],
        utc=True,
        errors="coerce",
        format="mixed",
    )
    data["captured"] = pd.to_datetime(
        data["crawled_at"],
        utc=True,
        errors="coerce",
        format="mixed",
    )
    data["likes"] = pd.to_numeric(data["likes"], errors="coerce")
    data = data.loc[data["published"].notna() & data["published"].le(cutoff)]
    data = data.loc[data["captured"].isna() | data["captured"].le(cutoff)]
    if yes(analysis["point_in_time"]):
        data = data.loc[data["captured"].notna()]
    data = data.sort_values(
        ["captured", "likes"], ascending=[False, False], na_position="last"
    ).drop_duplicates(["handle", "post_key"])
    local_dates = data["published"].dt.tz_convert(zone).dt.date
    if analysis["route"] == "show":
        show = pd.Timestamp(analysis["show_date"]).date()
        if cutoff.tz_convert(zone).date() < show + timedelta(days=37):
            raise ValueError("Full post-show baseline is not available by the cutoff.")
        sample_mask = local_dates.between(show, show + timedelta(days=7))
        baseline_mask = local_dates.between(
            show - timedelta(days=30), show - timedelta(days=1)
        ) | local_dates.between(show + timedelta(days=8), show + timedelta(days=37))
        reviewed = labels.loc[
            labels["handle"].str.lower().eq(analysis["handle"].lower())
        ].copy()
        if reviewed["post_key"].duplicated().any():
            raise ValueError("Collection review has duplicate post keys.")
        inclusion = data["post_key"].map(
            reviewed.set_index("post_key")["collection_related"]
        )
        if (
            inclusion.loc[sample_mask].isna().any()
            or not inclusion.loc[sample_mask]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin(
                ["true", "false", "yes", "no", "1", "0"],
            )
            .all()
        ):
            raise ValueError(
                "Classify all show-week posts as collection-related or not."
            )
        sample_mask &= inclusion.map(yes)
    elif analysis["route"] == "fiscal_year":
        start = pd.Timestamp(analysis["social_current_start"]).date()
        end = pd.Timestamp(analysis["social_current_end"]).date()
        previous_start = pd.Timestamp(analysis["social_baseline_start"]).date()
        previous_end = pd.Timestamp(analysis["social_baseline_end"]).date()
        if (
            start > end
            or previous_start > previous_end
            or previous_end >= start
            or end > cutoff.tz_convert(zone).date()
        ):
            raise ValueError("Social windows must be ordered, disjoint and complete.")
        if abs((end - start).days - (previous_end - previous_start).days) > 1:
            raise ValueError(
                "Compare equivalent social coverage, not partial vs full year."
            )
        sample_mask = local_dates.between(start, end)
        baseline_mask = local_dates.between(previous_start, previous_end)
    else:
        raise ValueError("route must be show or fiscal_year")
    valid = data["likes"].notna() & data["likes"].ge(0) & data["likes"].lt(math.inf)
    current = data.loc[sample_mask & valid, "likes"]
    baseline = data.loc[baseline_mask & valid, "likes"]
    minimum = int(analysis["min_posts"])
    if minimum < 1 or min(len(current), len(baseline)) < minimum:
        raise ValueError(
            f"Social samples too sparse: {len(current)}/{len(baseline)} posts"
        )
    median_current, median_baseline = float(current.median()), float(baseline.median())
    if median_baseline <= 0:
        raise ValueError("Baseline median is zero; social lift is undefined.")
    lift = (median_current / median_baseline - 1) * 100
    return {
        "current_post_count": len(current),
        "baseline_post_count": len(baseline),
        "current_median_likes": median_current,
        "baseline_median_likes": median_baseline,
        "social_lift_pct": lift,
        "social_score": clip_score(50 + lift),
        "unknown_capture_count": int(data["captured"].isna().sum()),
    }


def score_analysis(
    financials: pd.DataFrame,
    posts: pd.DataFrame,
    labels: pd.DataFrame,
    analysis: dict[str, Any],
    preview: bool = False,
) -> dict[str, Any]:
    if preview:
        analysis = {**analysis, "point_in_time": False}
    cutoff = pd.Timestamp(analysis["as_of"])
    if cutoff.tzinfo is None:
        raise ValueError("as_of must include a timezone.")
    result: dict[str, Any] = {
        **analysis,
        "ir_score": math.nan,
        "social_score": math.nan,
        "trend_score": math.nan,
        "fmi": math.nan,
        "classification": "Unavailable",
        "input_mode": "point-in-time"
        if yes(analysis["point_in_time"])
        else "descriptive/current-snapshot; not a historical forecast",
        "score_scope": analysis["proxy_label"]
        if yes(analysis["financial_proxy"])
        else "Named financial entity + brand social",
    }
    if preview:
        result.update(
            {
                "status": "PROVISIONAL — source-period proxy",
                "validated_collection_fmi": False,
                "point_in_time": False,
                "input_mode": "descriptive/current-snapshot; not a historical forecast",
                "limitations": (
                    "Unverified scope/units and source quarter allocation; assumed "
                    "selling-season proxy; caption suggestions; coverage and "
                    "engagement ages not verified; current snapshots, not "
                    "historical forecasts."
                ),
            }
        )
    gaps = []
    if analysis.get("preparation_gaps"):
        gaps.append(str(analysis["preparation_gaps"]))
    if yes(analysis["financial_proxy"]) and not str(analysis["proxy_label"]).strip():
        gaps.append("Proxy label is required.")
    for name in ("commercial/trend", "social"):
        try:
            if name == "commercial/trend":
                calculate = (
                    preview_commercial_components if preview else commercial_components
                )
                result.update(calculate(financials, analysis))
            else:
                result.update(
                    social_component(
                        posts, labels, analysis, require_review=not preview
                    )
                )
        except (ValueError, KeyError, TypeError, OverflowError) as error:
            gaps.append(f"{name}: {error}")
    scores = [result[key] for key in ("ir_score", "social_score", "trend_score")]
    if all(math.isfinite(s) for s in scores) and not gaps:
        result["fmi"] = 0.5 * scores[0] + 0.3 * scores[1] + 0.2 * scores[2]
        result["classification"] = band(result["fmi"])
    if math.isfinite(result["fmi"]) and not preview:
        try:
            entity = analysis["financial_entity"]
            target = _financial_row(
                financials,
                entity,
                "target",
                cutoff,
                yes(analysis["point_in_time"]),
            )
            latest = _financial_row(
                financials,
                entity,
                "latest",
                cutoff,
                yes(analysis["point_in_time"]),
            )
            if any(target[c] != latest[c] for c in ("metric", "scope", "currency")):
                raise ValueError(
                    "Baseline differs from actuals in scope/metric/currency."
                )
            if target["period_type"] != "quarter":
                raise ValueError(
                    "Target sales baseline must be an explicit fiscal quarter."
                )
            result["scenario_currency"] = target["currency"]
            result["target_period_start"] = target["period_start"]
            result["target_period_end"] = target["period_end"]
            last_year = math.nan
            try:
                historical = _financial_row(
                    financials,
                    entity,
                    "last_year_target",
                    cutoff,
                    yes(analysis["point_in_time"]),
                )
                if any(
                    target[c] != historical[c]
                    for c in ("metric", "scope", "currency", "period_type")
                ):
                    raise ValueError(
                        "Prior-year target sales have a different definition."
                    )
                for date_col in ("period_start", "period_end"):
                    if (
                        abs(
                            (
                                pd.Timestamp(target[date_col])
                                - (
                                    pd.Timestamp(historical[date_col])
                                    + pd.DateOffset(years=1)
                                )
                            ).days
                        )
                        > 14
                    ):
                        raise ValueError(
                            "Prior-year target is not the same fiscal quarter."
                        )
                last_year = historical["value"]
            except (ValueError, KeyError, TypeError) as error:
                gaps.append(f"forecast YoY unavailable: {error}")
            result.update(sales_scenario(result["fmi"], target["value"], last_year))
        except (ValueError, KeyError, TypeError) as error:
            gaps.append(f"sales scenario unavailable: {error}")
    result["gaps"] = " | ".join(gaps)
    result["interpretation"] = (
        "Planning assumption, not a causal estimate of social activity on revenue."
    )
    return result


def preview_periods(
    raw: pd.DataFrame,
    selections: pd.DataFrame,
    as_of: str,
) -> pd.DataFrame:
    """Select explicit native periods for a provisional ratio-only calculation.

    No invented currency, units, scope or fiscal boundaries. Never aggregate
    duplicate versions. These rows do NOT satisfy the reviewed FMI contract.
    """
    keys = ["entity", "year", "quarter", "classification"]
    if selections.duplicated(["entity", "period_role"]).any():
        raise ValueError("Choose one source period per entity/role.")
    candidates = raw.merge(selections, on=keys, how="inner")
    counts = candidates.groupby(["entity", "period_role"]).size()
    expected = pd.MultiIndex.from_frame(selections[["entity", "period_role"]])
    if not counts.reindex(expected, fill_value=0).eq(1).all():
        raise ValueError(
            "Missing or ambiguous source period; inspect native year/quarter rows."
        )
    if not candidates["metric"].eq("revenue").all():
        raise ValueError("Preview requires revenue rows.")
    values = pd.to_numeric(candidates["amount"], errors="coerce")
    if not (values.gt(0) & values.lt(math.inf)).all():
        raise ValueError("Preview requires finite positive revenue.")
    dates = pd.to_datetime(
        candidates["reported_date"], utc=True, errors="coerce", format="mixed"
    )
    cutoff = pd.Timestamp(as_of)
    if cutoff.tzinfo is None or dates.isna().any():
        raise ValueError("Use a timezone-aware cutoff and known source dates.")
    if (candidates["classification"].eq("Actual") & dates.gt(cutoff)).any():
        raise ValueError("Actual source period is later than the cutoff.")
    candidates["amount"] = values
    return candidates


def preview_collection_labels(
    posts: pd.DataFrame,
    reviews: pd.DataFrame,
    collection: str,
    other_collection: str,
) -> pd.DataFrame:
    """Caption suggestions for one preview; preserve user labels separately."""
    if not collection.strip() or not other_collection.strip():
        raise ValueError("Name the included and excluded collections.")
    labels = posts[["handle", "post_key", "description"]].copy()
    labels["collection_related"] = pd.Series(pd.NA, index=labels.index, dtype=object)
    captions = labels["description"].fillna("").str.casefold()
    included = captions.str.contains(collection.casefold(), regex=False)
    excluded = captions.str.contains(other_collection.casefold(), regex=False)
    labels.loc[included & ~excluded, "collection_related"] = True
    labels.loc[excluded & ~included, "collection_related"] = False
    labels["label_source"] = "Unknown: review caption/post"
    labels.loc[included ^ excluded, "label_source"] = "Provisional caption rule"
    if not reviews.empty:
        if reviews.duplicated(["handle", "post_key"]).any():
            raise ValueError("Collection review has duplicate post keys.")
        review_index = reviews.set_index(["handle", "post_key"])
        index = pd.MultiIndex.from_frame(labels[["handle", "post_key"]])
        manual = review_index["collection_related"].reindex(index)
        manual.index = labels.index
        valid = (
            manual.astype(str)
            .str.strip()
            .str.lower()
            .isin(["true", "false", "yes", "no", "1", "0"])
        )
        labels.loc[valid, "collection_related"] = manual.loc[valid].map(yes)
        labels.loc[valid, "label_source"] = "Existing user review"
    return labels


def comparison_analyses(
    analyses: pd.DataFrame, peers: pd.DataFrame
) -> list[dict[str, Any]]:
    """Expand configured brand-peer rows, not a global Cartesian product."""
    columns = ["brand", "financial_entity", "peer_entity"]
    if peers.empty or set(columns) - set(peers.columns):
        raise ValueError(
            "peers.csv needs brand, financial_entity and peer_entity rows."
        )
    pairs = peers.copy().fillna("")
    settings = analyses.copy().fillna("")
    for column in columns:
        pairs[column] = pairs[column].astype(str).str.strip()
        if pairs[column].eq("").any():
            raise ValueError(f"peers.csv has an empty {column}.")
    if pairs.duplicated(["financial_entity", "peer_entity"]).any():
        raise ValueError("Duplicate brand-peer comparison in peers.csv.")
    if pairs["financial_entity"].eq(pairs["peer_entity"]).any():
        raise ValueError("A brand cannot be its own peer.")
    if settings["financial_entity"].duplicated().any():
        raise ValueError("Use one analysis-settings row per financial entity.")
    settings = settings.set_index("financial_entity", drop=False)
    comparisons = []
    for pair in pairs.to_dict("records"):
        entity = pair["financial_entity"]
        if entity not in settings.index:
            raise ValueError(f"Add {entity} to inputs/analyses.csv.")
        analysis = settings.loc[entity].to_dict()
        if str(analysis["brand"]).strip() != pair["brand"]:
            raise ValueError(f"{entity}: brand name differs between input CSVs.")
        analysis.update(
            {
                "peer_entity": pair["peer_entity"],
                "peer_name": pair.get("peer_name", pair["peer_entity"]),
                "peer_rationale": pair.get("rationale", ""),
                "peer_limitations": pair.get("limitations", ""),
                "comparison_mode": "single-peer",
            }
        )
        # These legacy columns must not imply a two-peer benchmark in pair outputs.
        analysis.pop("peer_1", None)
        analysis.pop("peer_2", None)
        comparisons.append(analysis)
    return comparisons


def entity_period_choices(
    entities: pd.DataFrame,
    names: list[str],
    roles: tuple[str, ...] = ("oldest", "earlier", "latest"),
) -> pd.DataFrame:
    """Build explicit source-row selectors from entity fiscal-period CSV settings."""
    if entities["entity"].duplicated().any():
        raise ValueError("Use one entities.csv row per financial entity.")
    indexed = entities.set_index("entity")
    choices = []
    for entity in names:
        if entity not in indexed.index:
            raise ValueError(f"Add {entity} to inputs/entities.csv.")
        row = indexed.loc[entity]
        for role in roles:
            year = pd.to_numeric(row.get(f"{role}_year"), errors="coerce")
            quarter = str(row.get(f"{role}_quarter", "")).strip()
            if pd.isna(year) or year != int(year) or not 1 <= year <= 9999:
                raise ValueError(f"{entity}/{role}: configure a valid fiscal year.")
            if quarter not in {"Q1", "Q2", "Q3", "Q4"}:
                raise ValueError(f"{entity}/{role}: configure Q1, Q2, Q3 or Q4.")
            choices.append(
                {
                    "entity": entity,
                    "period_role": role,
                    "year": int(year),
                    "quarter": quarter,
                    "classification": "Forecast" if role == "target" else "Actual",
                }
            )
    return pd.DataFrame(choices)


def _comparison_peers(analysis: dict[str, Any]) -> list[str]:
    peers = (
        [analysis["peer_entity"]]
        if analysis.get("peer_entity")
        else [analysis["peer_1"], analysis["peer_2"]]
    )
    if len(set([analysis["financial_entity"], *peers])) != len(peers) + 1:
        message = (
            "Choose two distinct peers, excluding the scored entity."
            if len(peers) == 2
            else "Choose a distinct peer, excluding the scored entity."
        )
        raise ValueError(message)
    return peers


def revenue_components(
    values: dict[str, list[float]], entity: str, peers: list[str]
) -> dict[str, Any]:
    """Shared arithmetic; pairwise runs use one peer, legacy demo uses two."""
    latest_growth = {
        member: (rows[2] / rows[1] - 1) * 100 for member, rows in values.items()
    }
    earlier_growth = {
        member: (rows[1] / rows[0] - 1) * 100 for member, rows in values.items()
    }
    benchmark = float(pd.Series([latest_growth[p] for p in peers]).median())
    previous_benchmark = float(pd.Series([earlier_growth[p] for p in peers]).median())
    latest = latest_growth[entity] - benchmark
    earlier = earlier_growth[entity] - previous_benchmark
    trend, label = trend_score(latest, earlier)
    return {
        "brand_growth_pct": latest_growth[entity],
        "peer_growth_pct": benchmark,
        "peer_1_growth_pct": latest_growth[peers[0]],
        "peer_2_growth_pct": latest_growth[peers[1]] if len(peers) > 1 else math.nan,
        "peer_median_growth_pct": benchmark,
        "latest_relative_pp": latest,
        "earlier_relative_pp": earlier,
        "trend_change_pp": latest - earlier,
        "ir_score": clip_score(50 + 5 * latest),
        "trend_score": trend,
        "trend_label": label,
    }


def preview_commercial_components(
    financials: pd.DataFrame, analysis: dict[str, Any]
) -> dict[str, Any]:
    """Ratio-only source-period proxy; does not invent reviewed financial metadata."""
    peers = _comparison_peers(analysis)
    entity = analysis["financial_entity"]
    values = {}
    cutoff = pd.Timestamp(analysis["as_of"])
    for member in [entity, *peers]:
        amounts = []
        for role in ("oldest", "earlier", "latest"):
            selected = financials.loc[
                financials["entity"].eq(member) & financials["period_role"].eq(role)
            ]
            if len(selected) != 1:
                raise ValueError(f"{member}/{role}: select exactly one financial row")
            row = selected.iloc[0]
            amount = float(row["amount"])
            date = pd.to_datetime(row["reported_date"], utc=True, errors="coerce")
            if row["classification"] != "Actual" or row["metric"] != "revenue":
                raise ValueError(f"{member}/{role}: requires actual revenue")
            if not math.isfinite(amount) or amount <= 0:
                raise ValueError(f"{member}/{role}: requires positive finite revenue")
            if pd.isna(date) or date > cutoff:
                raise ValueError(f"{member}/{role}: invalid/future source date")
            amounts.append(amount)
        values[member] = amounts
    return revenue_components(values, entity, peers)


def demo_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Synthetic worked example. Never mixed with exported business data."""
    financials = []
    for entity, values in {
        "example_brand": [100, 104, 112.32],
        "example_peer_1": [100, 105, 109.2],
        "example_peer_2": [100, 105, 111.3],
    }.items():
        for role, year, amount in zip(
            ["oldest", "earlier", "latest"],
            [2023, 2024, 2025],
            values,
            strict=True,
        ):
            financials.append(
                {
                    "entity": entity,
                    "period_role": role,
                    "period_start": f"{year}-01-01",
                    "period_end": f"{year}-12-31",
                    "period_type": "annual",
                    "metric": "net_revenue",
                    "scope": "group",
                    "currency": "EUR",
                    "amount": amount,
                    "unit_multiplier": 1000000,
                    "classification": "Actual",
                    "published_at": f"{year + 1}-03-01",
                    "source": "SYNTHETIC",
                    "source_locator": "Handover worked example ratios",
                }
            )
    for role, year, amount, classification in (
        ("target", 2026, 100, "Forecast"),
        ("last_year_target", 2025, 102, "Actual"),
    ):
        financials.append(
            {
                "entity": "example_brand",
                "period_role": role,
                "period_start": f"{year}-10-01",
                "period_end": f"{year}-12-31",
                "period_type": "quarter",
                "metric": "net_revenue",
                "scope": "group",
                "currency": "EUR",
                "amount": amount,
                "unit_multiplier": 1000000,
                "classification": classification,
                "published_at": "2026-09-01",
                "source": "SYNTHETIC",
                "source_locator": "Illustrative target-quarter inputs",
            }
        )
    posts = pd.DataFrame(
        [
            {
                "handle": "example_brand",
                "post_key": f"{year}-{i}",
                "date_posted": f"{year}-06-{i + 1:02}T12:00:00Z",
                "likes": likes,
                "crawled_at": f"{year}-06-{i + 2:02}T12:00:00Z",
                "url": "https://example.com/synthetic",
            }
            for year, likes in [(2024, 10000), (2025, 13000)]
            for i in range(5)
        ]
    )
    analysis = {
        "brand": "SYNTHETIC EXAMPLE",
        "handle": "example_brand",
        "financial_entity": "example_brand",
        "peer_1": "example_peer_1",
        "peer_2": "example_peer_2",
        "route": "fiscal_year",
        "show_date": "",
        "timezone": "UTC",
        "social_current_start": "2025-01-01",
        "social_current_end": "2025-12-31",
        "social_baseline_start": "2024-01-01",
        "social_baseline_end": "2024-12-31",
        "min_posts": 5,
        "as_of": "2026-10-28T23:59:59Z",
        "point_in_time": True,
        "comparability_reviewed": True,
        "coverage_reviewed": True,
        "financial_proxy": False,
        "proxy_label": "",
    }
    labels = pd.DataFrame(
        columns=pd.Index(["handle", "post_key", "collection_related"]),
    )
    return pd.DataFrame(financials), posts, labels, analysis
