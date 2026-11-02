"""Human-readable run summary, derived from the delivered and coverage rows."""

from .models import Row


def official_run_note(audit: Row, dinner: Row, dossier_rows: list[Row]) -> str:
    rows = audit["prospect_coverage"]
    dossier_method = any(r.get("calculation_mode") == "dossier" for r in rows)
    scored = [r for r in rows if r.get("fmi_status") == "available"]
    dinner_ids = {r["brand_id"] for r in dinner.get("brands", [])}
    dinner_rows = [r for r in rows if r["brand_id"] in dinner_ids]
    dinner_scores = [r for r in scored if r["brand_id"] in dinner_ids]
    forecasts = [r for r in scored if r.get("adjusted_forecast") is not None]
    dinner_forecasts = [r for r in forecasts if r["brand_id"] in dinner_ids]
    missing = [r for r in dinner_rows if r.get("fmi_status") != "available"]
    policy = audit["policy"]
    dossier_forecasts = sum(r.get("baseline_revenue") is not None for r in dossier_rows)

    def cell(value: object) -> str:
        return str(value or "—").replace("|", "/").replace("\n", " ")

    def missing_inputs(row: Row) -> tuple[str, str]:
        findings, actions = [], []
        if row.get("latest_growth") is None or row.get("earlier_growth") is None:
            findings.append("No comparable three-quarter brand/parent revenue series")
            actions.append("Supply a same-scope revenue series and evidenced identity")
        if not row.get("used_peer_count"):
            findings.append("No usable assigned peers")
            actions.append("Map at least one comparable peer with both growth rates")
        if row.get("social_status") != "available":
            findings.append(
                "Usable likes posts current/baseline: "
                f"{row.get('current_usable_likes', 0)}/"
                f"{row.get('baseline_usable_likes', 0)}; "
                f"common months: {row.get('common_months', 0)}"
            )
            actions.append("Recover comparable social history for the selected windows")
        return (
            "; ".join(findings) or str(row.get("missing_reasons", "Unavailable")),
            "; ".join(actions) or str(row.get("score_next_step", "Review inputs")),
        )

    lines = [
        "# Official FMI presentation run",
        "",
        f"Source extraction (UTC): {audit['source_extracted_at']}. "
        f"Run ID: `{audit['run_id']}`.",
        "",
        "## Executive summary",
        "",
        f"- Coverage: evaluated all {len(rows)} prospects and all "
        f"{len(dinner_rows)} mandatory dinner brands. Delivered {len(scored)} "
        f"database-derived FMI scores, including {len(dinner_scores)} dinner brands. "
        f"{len(missing)} dinner brands remain unavailable.",
        "- Revenue: use the latest available native quarterly actual and the same "
        "season one and two years earlier. Calculate two YoY growth rates and "
        "compare both with the median of the same usable assigned peer set. "
        "One usable peer is sufficient. Missing peers and differing fiscal dates "
        "are disclosed.",
        f"- Social: Instagram median likes, collection days 0…+7 versus pooled "
        f"days −30…−1/+8…+37, minimum {policy['show_min_posts']} usable posts per "
        f"sample. Explicit annual/YTD windows require "
        f"{policy['annual_min_posts']} per sample and "
        f"{policy['annual_min_common_months']} common months. When configured, "
        "both annual samples are restricted to their common months before scoring.",
        f"- FMI: IR = clip(50 + {policy['ir_gap_multiplier']:g} × latest growth gap "
        "in pp); Social = "
        "clip(50 + likes lift in %); Trend follows the ordered ±2 pp change/"
        "persistent +5 pp rules. Raw FMI = "
        f"{policy['ir_weight']:.0%} IR + {policy['social_weight']:.0%} Social + "
        f"{policy['trend_weight']:.0%} Trend. "
        "Missing components never receive invented neutral values.",
        "- Display: rescale available headline raw scores to "
        f"{policy['display_lower']:g}–{policy['display_upper']:g}, rounded "
        "half-up to one decimal. Preserve the original raw classification.",
        f"- Forecast: apply both uplift methods independently to the same positive "
        f"current Q4 2026-compatible native forecast. {len(forecasts)} brands, "
        f"including {len(dinner_forecasts)} dinner brands, have adjusted forecasts. "
        "Native fiscal labels and dates remain visible. Legacy: raw ≤"
        f"{policy['legacy_uplift_threshold']:g} gives 0; otherwise "
        f"{policy['legacy_uplift_intercept']:.0%} + "
        f"{100 * policy['legacy_uplift_per_score']:g} pp per raw point above "
        f"{policy['legacy_uplift_threshold']:g}. New: "
        f"{policy['uplift_max']:g} × expm1({policy['uplift_exponent']:g} × "
        f"display/100) / expm1({policy['uplift_exponent']:g}).",
        f"- Dossier comparison: preserve {len(dossier_rows)} exact supplied report "
        f"headlines ({sum(r['brand_id'] in dinner_ids for r in dossier_rows)} "
        "dinner references), original raw values where established, printed "
        "components, arithmetic checks and period/source evidence. These are "
        "historical references, not like-for-like score changes. New dossier Q4 "
        f"scenarios exist for {dossier_forecasts} "
        "scope-matched current baselines; original report scores are unchanged.",
        "- App fields: both deliveries are one-sheet Excel tables with identical "
        "JSON row arrays. Columns include score drivers, revenue/growth/peer "
        "periods, social likes/comments/views and sample counts, forecast amounts, "
        "both uplifts, mappings, source IDs and quality flags. Context never "
        "changes the FMI weights. Field dictionaries and per-brand calculation "
        "records stay in `.work/fmi/`.",
        "",
        "## Dinner brands without a database-derived FMI",
        "",
        "| Brand | Missing inputs | Next action |",
        "|---|---|---|",
    ]
    for row in missing:
        reason, action = missing_inputs(row)
        lines.append(f"| {cell(row['name'])} | {cell(reason)} | {cell(action)} |")
    lines += [
        "",
        "## Verified configured parent and group selections",
        "",
        "Parent identities were queried on the separate authenticated Light/shared "
        "connections. An evidenced parent can supply missing brand financials, "
        "while social measurements remain the brand's. Explicit preferred-parent "
        "settings replace opaque private-brand series. Complete brand series "
        "otherwise remain selected. Minority investors are not reporting parents.",
        "",
        "| Brand | Financial subject | Selection | Latest actual end | FMI |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        if row.get("parent_name") or row.get("proxy"):
            selection = row.get("parent_fallback_status") or row.get("proxy_label")
            if row.get("proxy") and not row.get("parent_name"):
                selection = "explicit authorized group mapping (not parent fallback)"
            lines.append(
                f"| {cell(row['name'])} | {cell(row.get('financial_subject'))} | "
                f"{cell(selection)} | "
                f"{cell(row.get('latest_period_end'))} | "
                f"{cell(row.get('fmi_status'))} |"
            )
    lines += [
        "",
        "## Delivery limitations",
        "",
        "- Parent-group revenue and adjusted forecasts are NOT standalone brand "
        "amounts. Do not sum repeated group proxies across brands.",
        "- This is a current-source presentation simulation. Source publication "
        "and forecast vintages are not fully verified; it is not strict historical "
        "replay. Missing currency may use consistent same-subject source history "
        "or registry denomination, explicitly flagged as assumptions. Units and "
        "reporting scope are not invented; fiscal boundaries are labelled proxies.",
        "- Dynamic cohort rescaling can change an unchanged brand's uplift. "
        "The 70–98 range makes the new uplift positive for every available score. "
        "Both methods are business scenarios, not calibrated predictive accuracy.",
        "- Remaining missing source data, inadequate social samples, stale "
        "financials and absent forecast vintages require data-engineering work. "
        "See `../fmi-data-handoff.md` and its executed SQL companion for all brands.",
        "",
    ]
    if dossier_method:
        for i, line in enumerate(lines):
            if line == "# Official FMI presentation run":
                lines[i] = "# Official dossier-defined FMI run"
            elif line.startswith("- Revenue: use the latest"):
                lines[i] = (
                    "- Revenue: use the dossier's financial subject, scope and "
                    "explicit periods, independently of the Q4 forecast target. "
                    "Compare with the median of the same usable dossier-assigned "
                    "peers; one is sufficient. No latest-quarter substitution."
                )
            elif line.startswith("- Social: Instagram median likes"):
                lines[i] = (
                    "- Social: dossier-defined show/annual publication windows, "
                    "metric, collection filters and sample rules. Shows normally "
                    "use a preceding 15-day baseline and days 0…+7. Portfolio "
                    "methods take one lift per member, not pooled likes. "
                    "Unsupported platforms remain unavailable."
                )
            elif line.startswith("- FMI: IR ="):
                lines[i] = (
                    "- FMI: IR = clip(50 + configured multiplier × latest peer "
                    "gap in pp); Social = clip(50 + metric lift in %). Trend uses "
                    "the dossier's peer-gap/company-growth basis or labelled "
                    "assumption. Raw FMI weights are 50/30/20. Missing components "
                    "are not invented; percentile references require their cohort."
                )
            elif line.startswith("Parent identities were queried"):
                lines[i] = (
                    "Only an explicit dossier source identity routes a labelled "
                    "parent/segment proxy. Automatic parent fallback is disabled; "
                    "the forecast must match the selected financial subject/scope."
                )
            elif line.startswith("- This is a current-source presentation simulation"):
                lines[i] = (
                    "- This is a retrospective dossier-method calculation, not "
                    "point-in-time replay. Source periods/scope/currency/units "
                    "must be verified. Current captures and undated forecasts "
                    "cannot establish original historical information availability."
                )
    return "\n".join(lines)
