"""Read-only source coverage handoff, using the production scoring service."""

from collections import Counter
from dataclasses import asdict
from datetime import timedelta

from .collection import financial_candidates
from .inputs import as_dict
from .models import (
    FMIResult,
    Inputs,
    Row,
    Snapshot,
    calendar_date,
    fingerprint,
    instant,
    number,
    truth,
)
from .policy import Policy
from .scenario import FORECAST, series, year_ago
from .scoring import calculate
from .social import observations


def text(value: object) -> str:
    if value is None or value == "":
        return "missing"
    return str(value).replace("|", "\\|").replace("\n", " ")


def amount(value: object) -> str:
    parsed = number(value)
    return "missing" if parsed is None else f"{parsed:,.6f}".rstrip("0").rstrip(".")


def rate(value: object) -> str:
    parsed = number(value)
    return "missing" if parsed is None else f"{100 * parsed:.3f}%"


def joined(*values: object) -> str:
    return " / ".join(text(v) for v in values)


def mapping_hint(entity: Row, snapshot: Snapshot) -> str:
    """Expose exact registry candidates without substituting financial subjects."""
    candidates = [
        r
        for r in snapshot.metadata.get("candidate_mappings", [])
        if r["entity_id"] == entity["entity_id"]
    ]
    counts = Counter(
        p.get("company_code")
        for p in snapshot.financials
        if p.get("metric") == "revenue"
        and str(p.get("source_relation") or "").startswith(("light.", "ai."))
    )
    return (
        "; ".join(
            f"{text(r.get('company_name'))}: code {r['company_code']}, "
            f"ticker {text(r.get('company_ticker'))}, "
            f"retrieved Light revenue rows "
            f"{counts[r['company_code']]}"
            for r in candidates
        )
        or "no exact registry candidate; broader identity lookup needed"
    )


def table(headers: list[str], rows: list[list[object]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(text(v) for v in row) + " |" for row in rows),
        *([] if rows else ["| " + " | ".join("none" for _ in headers) + " |"]),
    ]


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        if number(value) is None:
            raise ValueError("SQL parameters must be finite")
        return str(value)
    if not isinstance(value, str):
        raise ValueError("Unsupported SQL audit parameter")
    # E-string also preserves literal backslashes in user-managed identifiers.
    return "E'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def query_pack(snapshot: Snapshot) -> str:
    """Export exactly the executed bounded SELECTs, with non-secret bind values."""
    lines = [
        "-- FMI data coverage: executed business SELECTs, not database credentials.",
        f"-- Extracted at {snapshot.metadata['extracted_at']}",
        "-- Run Light and shared sections on their SEPARATE database connections.",
        "-- Do not run as one script against either database.",
        "-- Python extractor discovers columns first and fails on row-limit overflow.",
        "-- This frozen SQL pack reflects the discovered schema at extraction time.",
    ]
    for source in ("Light", "shared"):
        lines.extend(
            [
                "",
                f"-- {source.upper()} CONNECTION SECTION",
                "BEGIN TRANSACTION READ ONLY;",
                "SELECT current_user AS database_role,",
                "       current_setting('transaction_read_only') AS read_only,",
                "       current_setting('default_transaction_read_only') "
                "AS default_read_only;",
            ]
        )
        for record in snapshot.metadata.get("queries", []):
            light = record["source_relation"].startswith(("light.", "ai."))
            if light != (source == "Light"):
                continue
            query = record["query"]
            if (
                not query.startswith("SELECT ")
                or ";" in query
                or not query.endswith(" LIMIT %s")
            ):
                raise ValueError("Only single bounded SELECT queries can be exported")
            values = [*record["scope"], snapshot.metadata["row_limit"] + 1]
            parts = query.split("%s")
            if len(parts) != len(values) + 1:
                raise ValueError("Query scope does not match bind parameters")
            rendered = parts[0] + "".join(
                sql_literal(v) + part for v, part in zip(values, parts[1:], strict=True)
            )
            lines.extend(
                [
                    f"-- {record['source_relation']}: "
                    f"{record['row_count']} source rows",
                    rendered + ";",
                ]
            )
        lines.append("ROLLBACK;")
    return "\n".join(lines) + "\n"


def windows(analysis: Row, values: Row) -> tuple[str, str]:
    if values.get("current_window"):
        return values["current_window"], values["baseline_window"]
    if analysis.get("route") == "show" and analysis.get("show_date"):
        show = calendar_date(analysis["show_date"])
        if analysis.get("calculation_mode") == "dossier":
            settings = analysis["dossier"]["social"]
            return (
                f"{show}/{show + timedelta(days=settings.get('current_days', 7))}",
                f"{show - timedelta(days=settings.get('baseline_days', 15))}/"
                f"{show - timedelta(days=1)}",
            )
        return (
            f"{show}/{show + timedelta(days=7)}",
            f"{show - timedelta(days=30)}/{show - timedelta(days=1)}; "
            f"{show + timedelta(days=8)}/{show + timedelta(days=37)}",
        )
    if analysis.get("route") == "annual":
        return (
            f"{text(analysis.get('current_start'))}/{text(analysis.get('current_end'))}",
            f"{text(analysis.get('baseline_start'))}/{text(analysis.get('baseline_end'))}",
        )
    end = calendar_date(analysis["forecast_target_end"])
    start = calendar_date(analysis["forecast_target_start"])
    return (
        f"{year_ago(start)}/{year_ago(end)}",
        f"{year_ago(start, 2)}/{year_ago(end, 2)}",
    )


def inventory_rows(rows: list[Row]) -> list[list[object]]:
    """Every distinct revenue candidate, no aggregation into annuals/quarters."""
    indexed: dict[tuple[str, ...], list[Row]] = {}
    for row in rows:
        if row.get("metric") != "revenue":
            continue
        key = tuple(
            text(row.get(k))
            for k in (
                "kind",
                "source_relation",
                "period_label",
                "source_classification",
            )
        ) + (text(row.get("reported_date") or row.get("date")),)
        indexed.setdefault(key, []).append(row)
    return [
        [
            kind,
            label,
            end,
            source,
            "; ".join(sorted({amount(r.get("amount")) for r in group})),
            "; ".join(sorted({text(r.get("currency")) for r in group})),
            classification,
            len(group),
        ]
        for (kind, source, label, classification, end), group in sorted(indexed.items())
    ]


def actions(result: FMIResult) -> list[str]:
    """Distinguish source backfill work from identity/policy/review decisions."""
    v = result.values
    tasks = []
    for reason in dict.fromkeys(result.gaps):
        if "unreviewed_parent_or_group_proxy" in reason:
            action = (
                "Owner decision: approve the intended reporting subject/proxy or "
                "map standalone brand data. Do not backfill parent revenue "
                "as brand revenue."
            )
        elif (
            "missing_or_ambiguous_light_registry" in reason
            or "ticker_conflicts" in reason
        ):
            action = (
                "Resolve company code/ticker/shared symbol against Light registry; "
                "do not join on company code alone."
            )
        elif "no_eligible_actual_quarter" in reason:
            action = (
                "Check the configured subject and source grain; no eligible quarterly "
                "actual was found. Annual/cumulative rows do not satisfy the "
                "current quarterly route."
            )
        elif reason.startswith("financial:"):
            action = (
                "Backfill/verify the specified actual quarter or resolve source "
                "conflicts, scope, units and currency; preserve provenance and "
                "native fiscal dates."
            )
        elif reason.startswith("peers:"):
            action = (
                "Owner decision: no peers are assigned. Select at least one "
                "suitable peer and resolve its identifiers "
                "before requesting a backfill."
                if not result.peers
                else "Provide three comparable actual quarters for at least "
                "one assigned "
                "peer, or have the owner select a suitable peer. One usable peer "
                "is sufficient; all peers need not be complete."
            )
        elif reason.startswith("social:"):
            action = (
                "Check exact handle/profile, publication dates and eligible capture "
                "timestamps; restore real post likes in the specified windows. "
                "Missing likes are not zero. Window/relevance changes require "
                "an owner decision, not invented data."
            )
        else:
            action = (
                "Resolve the upstream prerequisite documented above; "
                "do not impute a neutral component."
            )
        tasks.append(f"`{reason}` — {action}")
    if v.get("forecast_missing_reason"):
        reason = v["forecast_missing_reason"]
        action = (
            "Fix FMI prerequisites first; available baseline is not the blocker."
            if reason == "missing_available_display_fmi"
            else "Provide/verify a positive native revenue forecast within the "
            "target range, with a future end date and compatible reporting "
            "subject/currency/units."
        )
        tasks.append(f"`forecast:{reason}` — {action}")
    if v.get("baseline_revenue") is not None and v.get("prior_year_actual") is None:
        status = str(v.get("prior_year_actual_status") or "")
        repair = (
            "Match baseline/actual currency, units and reporting scope metadata; "
            "the actual may already be present. Do not backfill duplicate amounts."
            if "currency_units_or_scope_conflict" in status
            else "Supply/verify the compatible positive same-season prior-year actual."
        )
        tasks.append(
            f"Forecast YoY only: {repair} This does not block the uplift amount. "
            f"Status: `{v.get('prior_year_actual_status')}`."
        )
    return tasks


def brand_section(
    result: FMIResult,
    entity: Row,
    analysis: Row,
    entities: dict[str, Row],
    snapshot: Snapshot,
    policy: Policy,
) -> list[str]:
    v = result.values
    entity = {
        **entity,
        **{
            k: v[k]
            for k in (
                "light_code",
                "ticker",
                "shared_symbol",
                "financial_subject",
                "scope",
                "proxy_label",
            )
            if k in v
        },
    }
    raw = financial_candidates(entity, snapshot)
    handle = str(entity.get("handle") or "").lower().lstrip("@")
    captures = [
        p
        for p in snapshot.posts
        if handle and str(p.get("profile_username") or "").lower().lstrip("@") == handle
    ]
    matched = [
        p for p in captures if str(p.get("profile_id")) == str(entity.get("profile_id"))
    ]
    cutoff = instant(snapshot.metadata["extracted_at"])
    assert cutoff is not None
    retained, rejected = observations(matched, cutoff)
    cur, base = windows(analysis, v)
    minimum = (
        policy.show_min_posts if v.get("route") == "show" else policy.annual_min_posts
    )
    lines = [
        f"## {entity['name']} (`{entity['entity_id']}`)",
        "",
        f"Dinner mandatory: {truth(entity.get('fmi_required'))}. "
        f"Invited flag: {text(entity.get('event_invited'))}. "
        f"FMI: **{text(v.get('fmi_status'))}**. "
        f"Adjusted forecast: **{text(v.get('forecast_status'))}**.",
        "",
        "### Identity and dates",
        "",
        *table(
            ["Setting", "Value"],
            [
                [
                    "Light code / ticker / shared symbol",
                    joined(
                        entity.get("light_code"),
                        entity.get("ticker"),
                        entity.get("shared_symbol"),
                    ),
                ],
                [
                    "Financial subject / scope / proxy",
                    joined(
                        entity.get("financial_subject"),
                        entity.get("scope"),
                        entity.get("proxy_label"),
                    ),
                ],
                ["Identity status", v.get("identity_status")],
                [
                    "Parent fallback / ownership evidence",
                    joined(
                        v.get("parent_name"),
                        v.get("parent_fallback_status"),
                        v.get("parent_mapping_evidence"),
                    ),
                ],
                [
                    "Registry candidates (not approved replacements)",
                    mapping_hint(entity, snapshot),
                ],
                [
                    "Instagram handle / profile ID",
                    f"{text(entity.get('handle'))} / {text(entity.get('profile_id'))}",
                ],
                [
                    "Route / collection / show date",
                    joined(
                        v.get("route"),
                        analysis.get("collection"),
                        analysis.get("show_date"),
                    ),
                ],
                [
                    "Show/publication timezone",
                    v.get("timezone") or analysis.get("timezone") or "UTC",
                ],
                ["Original show/annual signal cutoff", analysis.get("cutoff")],
                [
                    "Measurement capture cutoff (current simulation)",
                    snapshot.metadata["extracted_at"],
                ],
                ["Current social publication windows (inclusive)", cur],
                ["Baseline social publication windows (inclusive)", base],
                [
                    "Requested forecast label / start / end",
                    joined(
                        analysis.get("forecast_target_label"),
                        analysis.get("forecast_target_start"),
                        analysis.get("forecast_target_end"),
                    ),
                ],
                [
                    "Selected forecast label / start proxy / native end",
                    joined(
                        v.get("baseline_period_label"),
                        v.get("baseline_period_start"),
                        v.get("baseline_period_end"),
                    ),
                ],
                [
                    "Forecast alignment / vintage",
                    joined(
                        v.get("forecast_calendar_alignment_status"),
                        v.get("forecast_vintage"),
                    ),
                ],
                [
                    "Latest actual age / freshness",
                    f"{text(v.get('latest_actual_age_days'))} days / "
                    f"{text(v.get('financial_freshness_status'))}",
                ],
            ],
        ),
        "",
        "### Data pulled and available",
        "",
        *table(
            [
                "Source",
                "Revenue actual candidates",
                "Revenue forecast candidates",
                "All metric candidates",
            ],
            [
                [
                    relation,
                    sum(
                        r.get("metric") == "revenue" and r.get("kind") == "actual"
                        for r in raw
                        if r["source_relation"] == relation
                    ),
                    sum(
                        r.get("metric") == "revenue" and r.get("kind") == "forecast"
                        for r in raw
                        if r["source_relation"] == relation
                    ),
                    sum(r["source_relation"] == relation for r in raw),
                ]
                for relation in sorted({r["source_relation"] for r in raw})
            ],
        ),
        "",
        f"Instagram: {len(captures)} capture rows for the handle; {len(matched)} "
        f"match the configured profile; {len(retained)} retained post observations "
        f"after cutoff filtering/deduplication; {len(rejected)} rejected capture "
        "observations (not necessarily distinct posts). "
        "Capture rows are not sample posts.",
        "",
        "### Revenue used for FMI",
        "",
        *table(
            [
                "Role",
                "Native label",
                "End",
                "Revenue",
                "Currency",
                "Unit multiplier",
                "Source / row ID",
                "Classification",
            ],
            [
                [
                    role,
                    v.get(f"{role}_period_label"),
                    v.get(f"{role}_period_end"),
                    amount(v.get(f"{role}_revenue")),
                    v.get(f"{role}_currency"),
                    v.get(f"{role}_unit_multiplier"),
                    "; ".join(
                        f"{r['source_relation']} / {r['source_row_id']}"
                        for r in result.financial_periods
                        if r.get("entity_id") == entity["entity_id"]
                        and r.get("metric") == "revenue"
                        and r.get("role") == role
                    ),
                    v.get(f"{role}_source_classification"),
                ]
                for role in ("oldest", "earlier", "latest")
            ],
        ),
        "",
        f"Earlier / latest YoY growth: {rate(v.get('earlier_growth'))} / "
        f"{rate(v.get('latest_growth'))}. Financial selection: "
        f"`{text(v.get('financial_selection_basis'))}`.",
        "",
        "### Assigned peers and usable subset",
        "",
        f"Used peers ({v.get('used_peer_count', 0)}): "
        f"{v.get('used_peer_names') or 'none'}. "
        "Calendar alignment: "
        f"`{text(v.get('peer_calendar_alignment_status'))}`. "
        "The same subset is used for both peer medians.",
        "",
    ]
    peer_rows = []
    for peer in result.peers:
        subject = entities[peer["peer_entity_id"]]
        selected, missing = series(
            subject, snapshot, analysis, policy.scenario_quarter_tolerance_days
        )
        peer_rows.append(
            [
                subject["name"],
                peer["status"],
                joined(
                    subject.get("light_code"),
                    subject.get("shared_symbol") or subject.get("ticker"),
                ),
                "; ".join(
                    f"{r['role']}: {text(r.get('period_label'))}, "
                    f"end {r['period_end']}, revenue {amount(r['amount'])}"
                    for r in selected
                ),
                rate(peer.get("earlier_growth")),
                rate(peer.get("latest_growth")),
                mapping_hint(subject, snapshot),
                peer.get("missing_reasons") or "; ".join(missing) or "none",
            ]
        )
    lines.extend(
        table(
            [
                "Peer",
                "Used/excluded",
                "Code / shared symbol",
                "Available selected periods",
                "Earlier growth",
                "Latest growth",
                "Registry candidate (not approved)",
                "Missing/exclusion reason",
            ],
            peer_rows,
        )
    )
    lines.extend(
        [
            "",
            "Peer-median growth earlier/latest: "
            f"{rate(v.get('earlier_peer_median_growth'))} / "
            f"{rate(v.get('latest_peer_median_growth'))}. "
            f"Brand gaps: {text(v.get('earlier_gap_pp'))} / "
            f"{text(v.get('latest_gap_pp'))} pp.",
            "",
            "### Social sample data",
            "",
            *table(
                [
                    "Sample",
                    "Total retained in window",
                    "Usable likes",
                    "Excluded",
                    "Median likes",
                    "Usable comments / median",
                    "Usable views / median",
                ],
                [
                    [
                        s,
                        v.get(f"{s}_total_posts"),
                        v.get(f"{s}_usable_posts"),
                        v.get(f"{s}_excluded_posts"),
                        amount(v.get(f"{s}_median_likes")),
                        joined(
                            v.get(f"{s}_usable_comments"),
                            amount(v.get(f"{s}_median_comments")),
                        ),
                        joined(
                            v.get(f"{s}_usable_views"),
                            amount(v.get(f"{s}_median_views")),
                        ),
                    ]
                    for s in ("current", "baseline")
                ],
            ),
            "",
            "Required usable likes per sample: "
            f"{minimum}. "
            f"Common months: {text(v.get('common_months'))} "
            f"(minimum {policy.annual_min_common_months} "
            "only for annual/period route). "
            f"Likes lift: {rate(v.get('likes_lift'))}. "
            f"Follower count/capture: {amount(v.get('follower_count'))} / "
            f"{text(v.get('follower_capture'))}.",
            "Window-post inclusion reasons: "
            f"{text(dict(Counter(p['inclusion_reason'] for p in result.social_posts)))}"
            ". "
            "Rejected capture reasons: "
            f"{text(dict(Counter(p['historical_status'] for p in rejected)))}.",
            "",
            "### FMI and forecast calculations",
            "",
            *table(
                ["Metric", "Value"],
                [
                    [
                        "IR / Social / Trend",
                        joined(
                            *(
                                amount(v.get(k))
                                for k in ("ir_score", "social_score", "trend_score")
                            )
                        ),
                    ],
                    [
                        "Trend change / rule",
                        f"{text(v.get('trend_change_pp'))} pp / "
                        f"{text(v.get('trend_label'))}",
                    ],
                    [
                        "Raw FMI / display FMI / raw class",
                        joined(
                            amount(v.get("raw_fmi")),
                            amount(v.get("display_fmi")),
                            v.get("raw_classification"),
                        ),
                    ],
                    [
                        "Forecast baseline / currency / multiplier",
                        joined(
                            amount(v.get("baseline_revenue")),
                            v.get("baseline_currency"),
                            v.get("baseline_unit_multiplier"),
                        ),
                    ],
                    [
                        "Forecast source / row ID",
                        joined(
                            v.get("baseline_source_relation"),
                            v.get("baseline_source_row_id"),
                        ),
                    ],
                    [
                        "Legacy uplift / absolute adjustment / adjusted forecast",
                        joined(
                            rate(v.get("legacy_uplift_fraction")),
                            amount(v.get("legacy_adjustment")),
                            amount(v.get("legacy_adjusted_forecast")),
                        ),
                    ],
                    [
                        "New uplift / absolute adjustment / adjusted forecast",
                        joined(
                            rate(v.get("uplift_fraction")),
                            amount(v.get("adjustment")),
                            amount(v.get("adjusted_forecast")),
                        ),
                    ],
                    [
                        "Forecast prior-year actual / period / end",
                        joined(
                            amount(v.get("prior_year_actual")),
                            v.get("prior_year_actual_period_label"),
                            v.get("prior_year_actual_period_end"),
                        ),
                    ],
                    [
                        "Baseline / new-adjusted forecast YoY",
                        joined(
                            rate(v.get("baseline_forecast_yoy")),
                            rate(v.get("adjusted_forecast_yoy")),
                        ),
                    ],
                ],
            ),
            "",
            "### Missing requirements and next actions",
            "",
        ]
    )
    tasks = actions(result)
    lines.extend(
        [f"- {t}" for t in tasks]
        or [
            "- No missing core simulation measurement; production reviews "
            "and vintages remain unverified."
        ]
    )
    lines.extend(
        [
            "",
            "Optional context (not FMI blockers): "
            + "; ".join(
                f"{key}={amount(v.get(key))}"
                for key in (
                    "latest_cost_of_revenue",
                    "latest_gross_profit",
                    "latest_ebitda",
                    "current_median_comments",
                    "baseline_median_comments",
                    "current_median_views",
                    "baseline_median_views",
                    "follower_count",
                )
            )
            + ". Missing optional metrics do not block FMI or uplift.",
            "",
            "<details>",
            "<summary>All pulled revenue candidates, "
            "including forecasts and underlying sources</summary>",
            "",
            *table(
                [
                    "Kind",
                    "Native label",
                    "Native end",
                    "Relation",
                    "Amount(s)",
                    "Currency",
                    "Classification",
                    "Rows",
                ],
                inventory_rows(raw),
            ),
            "",
            "</details>",
            "",
        ]
    )
    return lines


def build_handoff(
    inputs: Inputs, snapshot: Snapshot, policy: Policy
) -> tuple[str, Row]:
    if inputs.analyses and all(
        a.get("calculation_mode") == "dossier" for a in inputs.analyses
    ):
        from .dossier_coverage import build_handoff as dossier_handoff

        return dossier_handoff(inputs, snapshot, policy)
    if any(a.get("calculation_mode") != "presentation" for a in inputs.analyses):
        raise ValueError("Data handoff requires uniform dossier or presentation inputs")
    run_id = fingerprint(
        {
            "inputs": as_dict(inputs),
            "snapshot": asdict(snapshot),
            "policy": policy.model_dump(),
        }
    )
    results, cohort = calculate(inputs, snapshot, policy, run_id)
    entities = {e["entity_id"]: e for e in inputs.entities}
    analyses = {a["analysis_id"]: a for a in inputs.analyses}
    dinner = [r for r in results if truth(entities[r.brand_id].get("fmi_required"))]
    available = sum(r.values.get("fmi_status") == "available" for r in results)
    forecasts = sum(r.values.get("forecast_status") == "available" for r in results)
    lines = [
        "# FMI data-engineering handoff",
        "",
        f"Live database extraction: **{snapshot.metadata['extracted_at']}**. "
        f"Policy: `{policy.version}`. Diagnostic run: `{run_id}`.",
        "",
        "This report contains every prospect, including unavailable ones. It does "
        "not replace the filtered manager/app delivery or edit input mappings. "
        "Amounts are native source amounts, not FX-converted or summed across sources.",
        "",
        "## Peer rule verified",
        "",
        "With two assigned peers and one missing, FMI uses the one usable peer. "
        "Several usable peers use their median growth. The same subset must have "
        "both growth comparisons; zero usable peers blocks IR, Trend and FMI. "
        "Excluded peers do not otherwise block the score. Peer social data and "
        "peer forecasts are not required. The delivery columns are "
        "`used_peer_names`, `used_peer_count`, `used_peer_periods`, "
        "`peer_exclusion_reasons`. Strict replay additionally requires approved peers.",
        "",
        "## Query scope and interpretation",
        "",
        f"Connection context: `{text(snapshot.metadata.get('connection_context'))}`. "
        "Separate Light/shared clients verified transaction and default read-only on. "
        "Light retains ro; shared session read-only is not database-enforced grants.",
        f"Scoped years: {snapshot.metadata['first_year']}–"
        f"{snapshot.metadata['last_year']}; "
        f"maximum {snapshot.metadata['row_limit']:,} rows per relation; "
        "overflow fails. "
        "This is all retrieved data for the configured identifiers within these "
        "bounds, not proof that differently mapped data is absent from the database.",
        "Newest actual quarter plus same-native-quarter year-ago observations build "
        "growth. Year-ago drift allows 14 days. Latest dates may differ between "
        "peers. Forecast selects the nearest future quarter within 62 days of the "
        "requested end; native fiscal/retail labels are retained. Start dates are "
        "three-month proxies. Original document social windows are preserved.",
        "Missing source rows, invalid/comparable periods, identity/proxy review "
        "decisions and optional context are different problems. Do not fabricate "
        "quarterly revenue from annual/cumulative rows "
        "or fill missing likes with zero.",
        "Current financial vintages are unverified. Historical replay needs dated "
        "revenue and forecast evidence and eligible social captures by show+37. "
        "Comments/views/followers do not enter FMI. Uplift is a business scenario, "
        "not calibrated predictive accuracy; cohort rescaling changes uplift.",
        "",
        "## Calculation requirements",
        "",
        "Only brand revenue, at least one usable peer revenue series, and brand "
        "Instagram likes are required for FMI. Peer likes/forecasts are not required. "
        "A positive compatible brand forecast is needed for adjusted revenue, "
        "not for the score or uplift rate. Sample counts screen coverage, not "
        "statistical confidence.",
        "",
        "```text",
        "growth = current_revenue / prior_revenue - 1",
        "gap_pp = 100 * (brand_growth - median(used_peer_growth))",
        f"IR = clip(50 + {policy.ir_gap_multiplier:g} * latest_gap_pp, 0, 100)",
        "Social = clip(50 + 100 * "
        "(current_median_likes / baseline_median_likes - 1), 0, 100)",
        f"Trend: gap change > {policy.trend_change_boundary_pp:g} pp -> 70; "
        f"< -{policy.trend_change_boundary_pp:g} pp -> 30; "
        f"else both gaps >= {policy.sustained_gap_pp:g} pp -> 80; else 50",
        f"raw_FMI = {policy.ir_weight:.2f} * IR + "
        f"{policy.social_weight:.2f} * Social + {policy.trend_weight:.2f} * Trend",
        f"display_FMI = half_up({policy.display_lower:g} + "
        f"{policy.display_upper - policy.display_lower:g} * "
        "(raw_FMI - cohort_min) / (cohort_max - cohort_min), 1)",
        f"equal/single-score cohort -> {policy.display_equal:.1f}; "
        "unavailable headlines excluded",
        f"legacy_rate = 0 if raw_FMI <= {policy.legacy_uplift_threshold:g} "
        f"else {policy.legacy_uplift_intercept:g} + "
        f"{policy.legacy_uplift_per_score:g} * "
        f"(raw_FMI - {policy.legacy_uplift_threshold:g})",
        f"new_rate = {policy.uplift_max:g} * "
        f"expm1({policy.uplift_exponent:g} * display_FMI / 100) / "
        f"expm1({policy.uplift_exponent:g})",
        "adjustment = same_baseline * rate; adjusted_forecast = baseline + adjustment",
        "```",
        "",
        f"Cohort: {text(cohort.get('cohort_id'))}; "
        f"min/max raw FMI: {text(cohort.get('minimum'))} / "
        f"{text(cohort.get('maximum'))}. "
        "Changing membership can change an unchanged brand's uplift. "
        f"The {policy.display_lower:g}–{policy.display_upper:g} display range "
        "produces positive new rates with the current policy.",
        "",
        "## Coverage summary",
        "",
        f"{len(results)} prospects evaluated; **{available} FMI scores**, "
        f"**{forecasts} adjusted forecasts**. Mandatory dinner: {len(dinner)} brands; "
        f"{sum(r.values.get('fmi_status') == 'available' for r in dinner)} with FMI; "
        f"{sum(r.values.get('forecast_status') == 'available' for r in dinner)} "
        "with adjusted forecasts.",
        "",
        *table(
            [
                "Brand",
                "Dinner",
                "FMI",
                "Uplift amount",
                "Peers used",
                "Core missing requirements",
            ],
            [
                [
                    entities[r.brand_id]["name"],
                    truth(entities[r.brand_id].get("fmi_required")),
                    r.values.get("fmi_status"),
                    r.values.get("forecast_status"),
                    r.values.get("used_peer_names") or "none",
                    "; ".join(
                        dict.fromkeys(
                            [
                                *r.gaps,
                                *(
                                    ["forecast:" + r.values["forecast_missing_reason"]]
                                    if r.values.get("forecast_missing_reason")
                                    else []
                                ),
                            ]
                        )
                    )
                    or "none",
                ]
                for r in results
            ],
        ),
        "",
        "## Executed source queries",
        "",
        *table(
            ["Relation", "Source rows returned", "Columns retrieved"],
            [
                [q["source_relation"], q["row_count"], ", ".join(q["columns"])]
                for q in snapshot.metadata.get("queries", [])
            ],
        ),
        "",
        "Source/schema limitations:",
        "",
        *[f"- {text(s)}" for s in snapshot.metadata.get("limitations", [])],
        "",
        "## How to reproduce",
        "",
        "Run from the project root using configured aws-demos and aws-shared profiles. "
        "The SQL companion contains the exact executed SELECTs with scopes bound; "
        "run each connection section separately in read-only sessions. Prefer the "
        "CLI below for schema discovery and overflow checks.",
        "",
        "```sh",
        "uv run python -m aily_project.cli fmi extract "
        "--inputs scripts/fashion-momentum-index/inputs/FMI_inputs.json "
        "--output .work/fmi-data-check/snapshot.json",
        "uv run python -m aily_project.cli fmi data-handoff "
        "--inputs scripts/fashion-momentum-index/inputs/FMI_inputs.json "
        "--snapshot .work/fmi-data-check/snapshot.json "
        "--output outputs/fmi-data-handoff.md",
        "```",
        "",
    ]
    for result in results:
        analysis = analyses.get(result.analysis_id or "")
        if analysis is None:
            lines.extend(
                [
                    f"## {entities[result.brand_id]['name']}",
                    "",
                    "Missing one selected headline analysis; "
                    "owner must fix input configuration.",
                    "",
                ]
            )
            continue
        lines.extend(
            brand_section(
                result, entities[result.brand_id], analysis, entities, snapshot, policy
            )
        )
    peer_only = [e for e in inputs.entities if not truth(e.get("prospect"))]
    lines.extend(
        [
            "## Peer-only identity/source coverage",
            "",
            "These entities are not extra delivery prospects. Full period "
            "selection and exclusion reasons appear under each brand using them.",
            "",
        ]
    )
    lines.extend(
        table(
            [
                "Peer",
                "ID",
                "Light code",
                "Ticker / symbol",
                "Actual revenue candidates",
                "Forecast candidates (not required for peer)",
            ],
            [
                [
                    e["name"],
                    e["entity_id"],
                    e.get("light_code"),
                    f"{text(e.get('ticker'))} / {text(e.get('shared_symbol'))}",
                    sum(
                        r.get("metric") == "revenue" and r.get("kind") == "actual"
                        for r in financial_candidates(e, snapshot)
                    ),
                    sum(
                        r.get("metric") == "revenue"
                        and r.get("source_relation") == FORECAST
                        for r in financial_candidates(e, snapshot)
                    ),
                ]
                for e in peer_only
            ],
        )
    )
    return "\n".join(lines) + "\n", {
        "run_id": run_id,
        "cohort": cohort,
        "results": [r.record() for r in results],
    }
