"""Weighted-delivery comparison and app-facing metrics; never publishes content."""

import math
import unicodedata
from collections import Counter
from pathlib import Path

from .model import Row, truth
from .policy import half_up

CATEGORIES = ("LUXE", "FAST FOLLOWER", "RETAILER", "OTHER")


def rank_categories(rows: list[Row]) -> None:
    """Provisional delivery-only competition ranks on rounded display FMI."""
    for row in rows:
        row.update(
            leaderboard_rank=None,
            leaderboard_scored_count=None,
            leaderboard_member_count=None,
            leaderboard_basis="rounded display_fmi descending; competition ties; "
            "current dossier delivery only; not the historical/app board",
            leaderboard_status="excluded_from_delivery"
            if not row.get("include") or not row.get("has_dossier_data")
            else "missing_category_assignment"
            if not row.get("leaderboard_category")
            else "unsupported_category_assignment"
            if row["leaderboard_category"] not in CATEGORIES
            else "missing_fmi",
        )
    for category in CATEGORIES:
        members = [
            r
            for r in rows
            if r.get("include")
            and r.get("has_dossier_data")
            and r.get("leaderboard_category") == category
        ]
        scores = [r["display_fmi"] for r in members if r.get("display_fmi") is not None]
        for row in members:
            row["leaderboard_scored_count"] = len(scores)
            row["leaderboard_member_count"] = len(members)
            if row.get("display_fmi") is not None:
                row["leaderboard_rank"] = 1 + sum(
                    score > row["display_fmi"] for score in scores
                )
                row["leaderboard_status"] = "available_provisional_dossier_rank"


def leaderboards(rows: list[Row]) -> Row:
    """Flat handover boards, not publishable native app ranking objects."""
    boards = {}
    for category in CATEGORIES:
        members = [r for r in rows if r.get("leaderboard_category") == category]
        members.sort(
            key=lambda r: (
                r.get("leaderboard_rank") is None,
                r.get("leaderboard_rank") or 0,
                identity(r["name"]),
                r["brand_id"],
            )
        )
        boards[category] = {
            "scope": "current_dossier_delivery_only",
            "basis": "rounded display_fmi descending; competition ties",
            "member_count": len(members),
            "scored_count": sum(r.get("leaderboard_rank") is not None for r in members),
            "brands": [
                {
                    "brand_id": r["brand_id"],
                    "company_code": r.get("company_code"),
                    "name": r["name"],
                    "score": r.get("display_fmi"),
                    "rank": r.get("leaderboard_rank"),
                    "scope": r.get("scope"),
                    "dossier_score_basis": r.get("dossier_score_basis"),
                }
                for r in members
            ],
        }
    return boards


def identity(name: str) -> str:
    """Exact case/typographic matching only. No parent or fuzzy substitution."""
    return unicodedata.normalize("NFKC", name).casefold().replace("’", "'").strip()


def sentiment(score: float | None, component: str) -> str | None:
    if score is None:
        return None
    if component == "overall":
        return (
            "Good" if score >= 70 else "Neutral" if score >= 40 else "Needs improvement"
        )
    if component == "ir":
        return (
            "High"
            if score >= 75
            else "Medium"
            if score > 60
            else "Neutral"
            if score >= 40
            else "Low"
        )
    if component == "social":
        return "Positive" if score > 60 else "Neutral" if score >= 40 else "Negative"
    return {80: "Strong", 70: "Up and coming", 50: "Neutral", 30: "Fallback"}.get(
        score, "Source assessment"
    )


def comparison(row: Row, reference: Row | None) -> Row:
    """Reference columns observe final values; they never feed calculations."""
    if reference is None:
        return {"weighted_reference_match_status": "not_in_weighted_reference"}
    result = {"weighted_reference_" + k: v for k, v in reference.items()}
    pairs = [
        ("raw_fmi", "raw_fmi"),
        ("ir_score", "ir_score"),
        ("social_score", "social_score"),
        ("trend_score", "trend_score"),
    ]
    changed = []
    precision_only = []
    for current, old in pairs:
        a, b = row.get(current), reference.get(old)
        result["weighted_reference_" + current + "_difference"] = (
            a - b if a is not None and b is not None else None
        )
        if a is None or b is None:
            if a != b:
                changed.append(current + " availability")
        elif not math.isclose(a, b, abs_tol=1e-8):
            (precision_only if half_up(a) == half_up(b) else changed).append(current)
    if changed:
        status = "different_result"
    elif row.get("raw_fmi") is None:
        status = "both_headlines_unavailable"
    elif precision_only:
        status = "same_scores_at_reference_precision"
    else:
        status = "exact_scores"
    notes = []
    if changed:
        notes.append(
            "Different: "
            + ", ".join(changed)
            + ". "
            + (
                reference.get("method_note")
                or "Review source method, scope and selected cycle."
            )
        )
    if precision_only:
        notes.append(
            "Reference components are displayed to one decimal; "
            "dossier retains source precision."
        )
    if row.get("display_fmi") != reference.get("display_fmi"):
        notes.append(
            "New display uses the dossier cohort, not the historical 20–96 "
            "cohort or its explicit display overrides."
        )
    period_differences = [
        key
        for key in ("financial_period_start", "financial_period_end", "show_date")
        if row.get(key) is not None
        and reference.get(key) is not None
        and str(row[key]) != str(reference[key])
    ]
    result["weighted_reference_period_status"] = (
        "different_date_labels" if period_differences else "no_known_date_conflict"
    )
    if period_differences:
        notes.append(
            "Date labels differ: "
            + ", ".join(period_differences)
            + "; compare native fiscal boundaries with roadmap calendar/proxy labels."
        )
    result.update(
        weighted_reference_match_status=status,
        weighted_reference_comparison_reason=" ".join(notes)
        or "Score values match; document identity and evidence "
        "are not independently certified.",
    )
    return result


def enrich(rows: list[Row], reference: Row) -> list[Row]:
    """Readable cards/KPIs from current dossier metrics, not stale source copy."""
    lookup = reference.get("brands", {})
    result = []
    for source in rows:
        row = dict(source)
        row.update(comparison(row, lookup.get(identity(row["name"]))))
        if not reference:
            row["weighted_reference_match_status"] = "not_checked_no_reference"
        period = (
            row.get("financial_period_label")
            or row.get("collection")
            or "Dossier-selected period"
        )
        social_period = (
            f"{row['current_start']} to {row['current_end']}"
            if row.get("current_start") and row.get("current_end")
            else "Dossier-selected social window"
        )
        row["overall_sentiment"] = sentiment(row.get("raw_fmi"), "overall")
        for component in ("ir", "social", "trend"):
            row[component + "_sentiment"] = sentiment(
                row.get(component + "_score"), component
            )
        for component, value, label, unit, insight in (
            (
                "ir",
                row.get("latest_gap_pp"),
                "Growth vs. peer median",
                "pp",
                f"{period}: growth gap versus dossier peer median",
            ),
            (
                "social",
                row.get("social_lift_fraction"),
                "Median social metric change",
                "fraction",
                f"{social_period}: median "
                f"{row.get('social_metric') or 'social metric'} "
                "change versus dossier baseline",
            ),
            (
                "trend",
                row.get("latest_growth"),
                "Own revenue growth",
                "fraction",
                f"{period}: own revenue growth; "
                "numeric Strength uses dossier trend method",
            ),
        ):
            row[component + "_kpi"] = value
            row[component + "_kpi_label"] = label if value is not None else None
            row[component + "_descriptor"] = row.get(component + "_sentiment")
            metric = (
                f"{value * 100:+.1f}%"
                if value is not None and unit == "fraction"
                else f"{value:+.2f} pp"
                if value is not None
                else None
            )
            row[component + "_insight"] = (
                f"{insight}: {metric}."
                if metric
                else f"{period}: dossier {component} score "
                f"{row[component + '_score']:g}/100; underlying KPI unavailable."
                if row.get(component + "_score") is not None
                else None
            )
        raw, display = row.get("raw_fmi"), row.get("display_fmi")
        row["one_core_insight"] = (
            f"{row['name']}: dossier FMI {raw:g}/100, normalized {display:.1f}; "
            f"{row['score_method']} method."
            if raw is not None and display is not None
            else f"{row['name']}: complete dossier FMI unavailable "
            f"({row.get('fmi_status')})."
        )
        result.append(row)
    return result


def app_plan(rows: list[Row]) -> Row:
    """Native content candidates are kept separate from the flat delivery JSON."""
    reports = []
    for row in rows:
        if row.get("raw_fmi") is None:
            continue
        history = []
        for year in (2023, 2024, 2025, 2026):
            sales, attention = (
                row.get(f"source_sales_{year}"),
                row.get(f"source_social_{year}"),
            )
            if sales is not None or attention is not None:
                history.append(
                    {
                        "year": str(year),
                        "attention": f"{attention * 100:+.1f}% source social change; "
                        "source-specific windows"
                        if attention is not None
                        else "Unavailable in dossier",
                        "revenue": f"{sales:,.3f} source Q4 amount; "
                        "see source period/scope notes"
                        if sales is not None
                        else "Unavailable in dossier",
                    }
                )
        content = {
            "schemaVersion": 1,
            "domain": row.get("app_domain"),
            "name": row["name"],
            "category": row.get("app_category"),
            "openingLine": "Fashion Momentum Index",
            "scoreStatus": "Dossier snapshot; business scenario, "
            "not historical replay. "
            + str(row.get("dossier_score_basis") or row.get("score_method")),
            "oneCoreInsight": row["one_core_insight"],
            "overall": {
                "score": row["raw_fmi"],
                "normalizedScore": row["display_fmi"],
                "sentiment": row["overall_sentiment"],
            },
            "revenueMethodology": [
                str(
                    row.get("scope")
                    or "Dossier-reported score; financial scope requires review"
                ),
                str(row.get("source_document")),
                "New normalization uses this dossier cohort. "
                "Exponential uplift is a business scenario; undated forecasts "
                "do not establish historical availability.",
                str(
                    row.get("forecast_source_notes")
                    or "Forecast baseline evidence is shown in the delivery."
                ),
            ],
            "allowRankingPreview": False,
        }
        for component, native in (
            ("ir", "momentum"),
            ("social", "social"),
            ("trend", "strength"),
        ):
            value = row.get(component + "_score")
            if value is not None:
                kpi = row.get(component + "_kpi")
                content[native] = {
                    "score": value,
                    "sentiment": row[component + "_sentiment"],
                    "descriptor": row[component + "_descriptor"],
                    "insight": row[component + "_insight"],
                    "kpi": (
                        f"{kpi:+.2f} pp" if component == "ir" else f"{kpi * 100:+.1f}%"
                    )
                    if kpi is not None
                    else None,
                    "kpiLabel": row[component + "_kpi_label"],
                }
        amount = row.get("adjusted_forecast")
        content["projection"] = {
            "displayValue": f"{row.get('baseline_currency')} {amount:,.3f} × "
            f"{row.get('baseline_unit_multiplier'):g}"
            if amount is not None
            else "Adjusted forecast unavailable",
            "sentiment": "Business scenario" if amount is not None else "Unavailable",
            "descriptiveInsight": (
                f"{row.get('forecast_target_label') or 'Target period unavailable'}: "
                "exponential scenario on the approved unadjusted baseline; "
                f"{row['forecast_status']}."
            ),
            "statisticalInsight": None,
            "history": history,
        }
        issues = []
        if not row.get("app_company_code"):
            issues.append(
                "Approve exact existing tenant company_code; "
                "ticker is not a company code"
            )
        if not row.get("app_domain") or row.get("app_domain") == "example.invalid":
            issues.append(
                "Approve primary website domain; email domain is not inferred"
            )
        if row.get("app_category") not in {"LUXE", "PREMIUM", "MASS_MARKET"}:
            issues.append(
                "Approve app category; FAST FOLLOWER/RETAILER/OTHER "
                "have no automatic mapping"
            )
        if "momentum" not in content or "social" not in content:
            issues.append(
                "Required native Momentum/Social signals unavailable; "
                "no neutral substitution"
            )
        if not history:
            issues.append(
                "Native projection history requires at least one supported year"
            )
        if not truth(row.get("app_content_approved")):
            issues.append("Approve generated copy, proxy scope and dossier methods")
        reports.append(
            {
                "brand_id": row["brand_id"],
                "company_code": row.get("app_company_code"),
                "reference_company_codes": row.get("weighted_reference_company_codes"),
                "title": "Fashion Momentum Index",
                "renderer": "native",
                "html": None,
                "content_candidate": content,
                "content_json": content if not issues else None,
                "status": "local_content_reviewed" if not issues else "blocked",
                "blockers": issues,
            }
        )
    return {
        "execution": "plan",
        "live_writes_performed": False,
        "schema_reference": "aily-saas-app refs/pull/29147/head "
        "mobile/app/v3/modules/superagent/fashionMomentum/model.ts; "
        "verify deployed version before apply",
        "target": None,
        "release_status": "App PR29147 open at check on 2026-11-02; "
        "main model unavailable; deployed release not verified",
        "artwork": "preserve",
        "rankings": "preserve",
        "publication": "not_authorized",
        "required_before_apply": [
            "Target tenant/environment and authorized connections",
            "DB migrations 7b65703b9c02/c34ef91b802d, "
            "DataAPI/BFF/mobile deployment evidence",
            "Existing tenant company keys and content approvals",
            "Renderer/artwork/ranking/publication choices",
            "Before-images and rollback location outside Git",
            "Explicit apply approval",
        ],
        "reports": reports,
    }


def save_handoff(rows: list[Row], reference: Row, output: Path) -> None:
    """Comparison only. The receiving team owns app content and uploading."""
    counts = Counter(r.get("weighted_reference_match_status") for r in rows)
    common = [r for r in rows if r.get("weighted_reference_name")]
    raw_matches = sum(
        r.get("raw_fmi") is not None
        and r["raw_fmi"] == r.get("weighted_reference_raw_fmi")
        for r in common
    )
    historical_scored = sum(
        r.get("raw_fmi") is not None for r in reference.get("brands", {}).values()
    )
    represented_scored = sum(
        r.get("weighted_reference_raw_fmi") is not None for r in common
    )
    raw_differences = sum(
        r.get("raw_fmi") is not None
        and r.get("weighted_reference_raw_fmi") is not None
        and r["raw_fmi"] != r["weighted_reference_raw_fmi"]
        for r in common
    )
    further_differences = counts["different_result"] - raw_differences
    source_checks = [
        r["source_projection_difference"]
        for r in rows
        if r.get("source_projection_difference") is not None
    ]
    source_max_difference = max(map(abs, source_checks), default=0)
    lines = [
        "# Dossier vs historical weighted delivery",
        "",
        "Original dossier values, historical reference and database automation "
        "are unchanged. This comparison does not certify identical "
        "source documents or reporting scope.",
        "",
        f"Delivery: {len(rows)} rows, "
        f"{sum(r.get('raw_fmi') is not None for r in rows)} FMI scores. "
        f"Comparison counts: {dict(counts)}.",
        f"{len(common)} overlapping brands; {raw_matches} identical available "
        f"raw FMIs. {represented_scored}/{historical_scored} historically scored "
        f"brands are represented. {raw_differences} raw scores differ; "
        f"{further_differences} further differences concern coverage/partial "
        "components. See component and method columns below.",
        f"{len(source_checks)} source legacy forecasts reproduced from untreated "
        "baselines; maximum absolute difference "
        f"{source_max_difference:.3g} native currency units. "
        + (
            "Floating-point precision only."
            if source_max_difference < 1e-8
            else "Review source formula/period/baseline differences."
        ),
        "",
        "## Method differences",
        "",
        "- The roadmap Strength rule gives 80 for gap improvement >2 pp when "
        "the latest gap is nonnegative, otherwise 70. Some source dossiers "
        "instead use company-only trend or different component methods.",
        "- The historical normalization cohort is 20–96, with explicit "
        "Estée Lauder and ME+EM revisions. Our new cohort is recorded in "
        "delivery JSON; source display scores are retained separately.",
        "- Source sales projections may apply legacy uplift to their "
        "source-normalized FMI. Our legacy rate uses dossier raw FMI. "
        "Source legacy diagnostic reproduces the source-normalized rate. "
        "The exponential uses our rounded normalized FMI. Already projected "
        "source revenue is never used as baseline.",
        "- No score is changed just to reproduce the old workbook. Historical "
        "one-off revisions, manual descriptors and stale narratives "
        "stay reference-only.",
        "",
        "| Brand | Dossier FMI | Weighted FMI | Dossier IR / Social / Trend | "
        "Weighted IR / Social / Strength | New display | Weighted display | Reason |",
        "|---|---:|---:|---|---|---:|---:|---|",
    ]

    def show(v):
        if v is None:
            return "—"
        if isinstance(v, (int, float)):
            return f"{v:.4g}"
        return str(v).replace("|", "/").replace("\n", " ")

    for r in rows:
        if r.get("weighted_reference_name"):
            values = [
                r["name"],
                r.get("raw_fmi"),
                r.get("weighted_reference_raw_fmi"),
                " / ".join(
                    show(r.get(k + "_score")) for k in ("ir", "social", "trend")
                ),
                " / ".join(
                    show(r.get("weighted_reference_" + k + "_score"))
                    for k in ("ir", "social", "trend")
                ),
                r.get("display_fmi"),
                r.get("weighted_reference_display_fmi"),
                r.get("weighted_reference_comparison_reason"),
            ]
            lines.append("| " + " | ".join(show(v) for v in values) + " |")
    lines += [
        "",
        "## Data handover",
        "",
        "Share the one-sheet Excel and matching typed JSON. company_code is "
        "the verified Light retrieval key; ticker/shared symbol and financial "
        "proxy subject remain separate. Unresolved keys have explicit statuses. "
        "The receiving team owns native/HTML presentation and app upload under "
        "fashion-momentum-agent-handoff.md; no upload plan or cloud writes run "
        "during delivery generation.",
        "",
        f"Reference: {reference.get('source', 'Not supplied')}",
    ]
    (output / "weighted-comparison.md").write_text("\n".join(lines) + "\n")
