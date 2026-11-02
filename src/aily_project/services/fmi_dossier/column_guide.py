"""Presentation-only column dictionary; no alternative calculation path."""

from .model import Field, Row

RECOMMENDED = {
    "name",
    "company_code",
    "one_core_insight",
    "overall_sentiment",
    "raw_fmi",
    "display_fmi",
    "ir_score",
    "social_score",
    "trend_score",
    "ir_kpi",
    "social_kpi",
    "trend_kpi",
    "ir_kpi_label",
    "social_kpi_label",
    "trend_kpi_label",
    "leaderboard_category",
    "leaderboard_rank",
    "forecast_target_label",
    "baseline_subject",
    "baseline_currency",
    "baseline_unit_multiplier",
    "baseline_revenue",
    "uplift_fraction",
    "adjustment",
    "adjusted_forecast",
    "prior_year_forecast",
    "baseline_forecast_vs_py_forecast_yoy",
    "adjusted_forecast_vs_py_forecast_yoy",
    "fmi_increment_vs_py_forecast_pp",
}
QUALIFICATIONS = {
    "brand_id",
    "fmi_status",
    "forecast_status",
    "missing_reasons",
    "baseline_is_parent_proxy",
    "baseline_scope",
    "baseline_source",
    "forecast_target_start",
    "forecast_target_end",
    "forecast_native_period_label",
    "forecast_vintage_status",
    "prior_year_forecast_comparison_status",
    "historical_eligibility",
    "scope",
    "financial_subject",
    "social_metric",
    "social_platform",
    "social_handle",
    "app_category",
    "dossier_score_basis",
}
DETAILS = {
    "name": (
        "Brand/prospect name. Parent financial subjects remain separately labelled."
    ),
    "company_code": (
        "Verified Light company retrieval key. Never use ticker, brand_id or a "
        "parent key as the brand app key."
    ),
    "raw_fmi": (
        "Published headline when score_source=published_delivery, otherwise "
        "selected dossier headline. Reported mode "
        "preserves the printed score; weighted mode uses supplied components. "
        "May already represent a source percentile method."
    ),
    "display_fmi": (
        "Published normalized FMI is preserved for existing scored brands. Other "
        "brands use current cohort rescaling, 70–98, half-up one decimal. "
        "This is the input to NEW exponential uplift, not source_display_fmi."
    ),
    "ir_score": (
        "Published or selected dossier IR/Momentum score, 50% weight. "
        "Displayed as Trend / Peer Trajectory. "
        "Accepted source score, not freshly recomputed from rounded growth."
    ),
    "social_score": (
        "Published or selected dossier Social/Show Attention score, 30% weight. "
        "Measures the source-defined "
        "attention metric, not audience sentiment."
    ),
    "trend_score": (
        "Published or selected dossier Strength/Commercial Pace score, 20% weight. "
        "Not the IR component despite its internal trend name."
    ),
    "ir_kpi": (
        "Published card KPI for existing scored brands; otherwise latest brand "
        "growth minus selected peer-median growth, in percentage points. "
        "KPI is distinct from the 0–100 IR score."
    ),
    "social_kpi": (
        "Published card KPI for existing scored brands; otherwise current median "
        "social metric divided by baseline median minus one. "
        "Use with social_metric/platform and source windows; "
        "it is not necessarily likes for every dossier."
    ),
    "trend_kpi": (
        "Published card KPI for existing scored brands; otherwise own latest "
        "revenue growth, a fraction. Context for the Commercial Pace "
        "card, not a recalculation of source Strength."
    ),
    "leaderboard_category": (
        "Current company-list column B: LUXE, PREMIUM or MASS_MARKET. "
        "Unlisted brands have a blank category and no rank; no inferred conversion."
    ),
    "leaderboard_rank": (
        "Competition rank on rounded display FMI within the delivered category. "
        "Ties share rank. This is not the live app ranking."
    ),
    "forecast_target_label": (
        "Read this before calling the scenario Q4. Includes the selected native "
        "fiscal/calendar quarter or labelled fiscal proxy; it may not be calendar Q4."
    ),
    "baseline_subject": (
        "Financial company/parent whose untreated forecast is uplifted. "
        "Read with parent-proxy flag and baseline_scope."
    ),
    "baseline_currency": (
        "Currency of baseline, adjustment, adjusted forecast and comparable PY "
        "forecast. No FX conversion is performed."
    ),
    "baseline_unit_multiplier": (
        "Multiply stored forecast amounts by this number to obtain full currency "
        "units. 1,000,000 means amounts are displayed in millions."
    ),
    "baseline_revenue": (
        "Untreated current-target revenue forecast, BEFORE FMI. "
        "This is neither last year's actual nor the social comparison baseline."
    ),
    "uplift_fraction": (
        "NEW exponential scenario rate, evaluated at rounded current normalized FMI. "
        "Defaults: zero at score ≤60; otherwise 3% + 8% × expm1((score−60)/40). "
        "No 11% cap."
    ),
    "adjustment": (
        "NEW absolute forecast increase: untreated baseline × new uplift fraction. "
        "Same currency and multiplier as baseline."
    ),
    "adjusted_forecast": (
        "NEW forecast amount: untreated baseline + new adjustment. "
        "Recommended forecast headline. Never uplift the old source projection again."
    ),
    "prior_year_forecast": (
        "Comparable prior target-year FORECAST from the saved Light snapshot, "
        "in baseline units. Not PY actual sales or an archived forecast "
        "as originally issued."
    ),
    "baseline_forecast_vs_py_forecast_yoy": (
        "Current-target forecast growth BEFORE FMI versus matching PY FORECAST: "
        "baseline_revenue / prior_year_forecast − 1. Compare AW to this AV field."
    ),
    "adjusted_forecast_vs_py_forecast_yoy": (
        "NEW Q4/selected-target forecast growth AFTER exponential FMI versus matching "
        "PY FORECAST: adjusted_forecast / prior_year_forecast − 1. "
        "USE THIS, not historical AL. Positive uplift increases it versus AV, "
        "but it may still be negative."
    ),
    "fmi_increment_vs_py_forecast_pp": (
        "Additional forecast YoY from FMI: 100 × (NEW adjusted YoY − baseline YoY), "
        "in percentage points. It is not the uplift rate; uplift uses "
        "the current baseline denominator."
    ),
    "source_q4_sales_yoy_2026": (
        "OLD frozen 2026 source projection versus PY Q4 SALES. Original AL, "
        "not the new exponential scenario or forecast-versus-forecast YoY. "
        "Do not use as the new commercial headline."
    ),
    "source_q4_vs_baseline_2026": (
        "OLD frozen original uplift/source projection beat versus its same-year "
        "baseline. Original AG. Does not update when NEW exponential policy changes."
    ),
    "source_display_fmi": (
        "FMI in the original sales workbook, used only to reproduce its legacy "
        "formula. Not current normalized score S or historical weighted score S."
    ),
    "source_projected_forecast": (
        "Frozen original sales-workbook legacy-adjusted projection. "
        "Comparison only; never the starting forecast to uplift again."
    ),
    "source_legacy_uplift_fraction": (
        "Old linear formula evaluated at original sales-workbook FMI. "
        "Legacy comparison only, not the new rate AR."
    ),
    "source_legacy_adjusted_forecast": (
        "Old formula reproduced from original sales-workbook FMI on the same "
        "untreated baseline. Compare with new AT, but keep period/denominator "
        "differences explicit."
    ),
    "legacy_adjusted_forecast": (
        "Diagnostic old formula evaluated at current RAW FMI, not the original "
        "workbook display. Not necessarily the forecast in the "
        "historical weighted file."
    ),
    "legacy_uplift_fraction": (
        "Diagnostic raw-score legacy rate: zero at raw ≤60, otherwise "
        "3% + (raw−60)×0.2%. Not the exponential headline."
    ),
    "adjusted_forecast_yoy": (
        "NEW forecast divided by approved comparable PY ACTUAL minus one. "
        "Different denominator from AW; leave blank without comparable actuals."
    ),
    "baseline_forecast_yoy": (
        "Untreated forecast divided by approved comparable PY ACTUAL minus one. "
        "Different denominator from AV."
    ),
    "reported_fmi": (
        "Printed dossier headline; feeds raw_fmi only in reported mode. "
        "Other score alternatives remain separate."
    ),
    "weighted_component_fmi": (
        "Supplied IR×50% + Social×30% + Strength×20%. Diagnostic in reported mode; "
        "headline only in explicit weighted_components mode."
    ),
    "reported_component_difference": (
        "Weighted component total minus printed headline. Rounding or different "
        "source methods can explain nonzero differences; "
        "no automatic source-score replacement."
    ),
    "overall_sentiment": (
        "App label from selected raw score: Good ≥70, Neutral ≥40, "
        "otherwise Needs improvement. Separate from detailed raw classification."
    ),
    "one_core_insight": (
        "Published narrative for existing scored brands; otherwise generated "
        "from final raw/normalized scores and method; "
        "states the missing reason instead when no headline is available."
    ),
    "oldest_revenue": (
        "Oldest of the three source-selected comparable revenue observations. "
        "Use with currency, unit multiplier, financial subject "
        "and source period evidence."
    ),
    "earlier_revenue": (
        "Middle of the three source-selected comparable revenue observations. "
        "Denominator for latest growth and numerator for earlier growth."
    ),
    "latest_revenue": (
        "Latest source-selected comparable revenue observation, not forecast baseline. "
        "Read selected financial dates, currency, multiplier and brand/parent scope."
    ),
    "earlier_growth": (
        "Earlier comparable revenue growth: earlier / oldest − 1 if derived; "
        "printed source growth takes precedence. Fraction, not percentage points."
    ),
    "latest_growth": (
        "Latest comparable revenue growth: latest / earlier − 1 if derived; "
        "printed source growth takes precedence. Also drives Commercial Pace KPI."
    ),
    "earlier_gap_pp": (
        "Earlier brand revenue growth minus earlier peer-median growth, in pp. "
        "Part of trajectory context, not a newly calculated dossier score."
    ),
    "latest_gap_pp": (
        "Latest brand revenue growth minus latest peer-median growth, in pp. "
        "Displayed as IR KPI. Does not replace the source's accepted IR score."
    ),
    "baseline_median_metric": (
        "Median per-post social metric in the dossier baseline sample. "
        "Read social_metric, platform, sample dates/counts and relevance evidence."
    ),
    "current_median_metric": (
        "Median per-post social metric in the dossier current sample. "
        "Compare only to the matching baseline metric/window method."
    ),
    "baseline_posts": "Source baseline sample post count; not follower count.",
    "current_posts": "Source current sample post count; not follower count.",
    "baseline_start": "Start of the dossier-selected social baseline window.",
    "baseline_end": "End of the dossier-selected social baseline window.",
    "current_start": "Start of the dossier-selected current social sample window.",
    "current_end": "End of the dossier-selected current social sample window.",
    "social_lift_fraction": (
        "Social sample lift: current median / baseline median − 1 if derived; "
        "printed source value takes precedence. Fraction, not score points."
    ),
}


def column_letter(index: int) -> str:
    """One-based Excel column label; calculated from actual exported order."""
    label = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        label = chr(65 + remainder) + label
    return label


def delivery_use(key: str) -> str:
    if key in RECOMMENDED:
        return "Recommended delivery"
    if key in QUALIFICATIONS:
        return "Delivery qualification"
    if key.startswith(("legacy_", "source_legacy_")):
        return "Legacy comparison only"
    if key.startswith(("weighted_reference_", "source_")) or key in {
        "weighted_component_fmi",
        "reported_component_difference",
    }:
        return "Historical / audit only"
    return "Supporting app context"


def build_column_guide(fields: list[Field]) -> Row:
    """Document every exported field, preserving its source and actual location."""
    positions = {f.key: column_letter(i) for i, f in enumerate(fields, 1)}
    rows = []
    for field in fields:
        rows.append(
            {
                "column": positions[field.key],
                "key": field.key,
                "header": field.label,
                "use": delivery_use(field.key),
                "meaning": DETAILS.get(
                    field.key, f"{field.description or field.label}. {field.derivation}"
                ),
                "calculation": field.derivation,
                "source": field.source_reference,
                "inputs": "; ".join(
                    f"{key} ({positions[key]})" if key in positions else key
                    for key in field.source_fields
                ),
                "type_unit": f"{field.type}; {field.unit}",
                "score_input": "Yes" if field.influences_fmi else "No",
            }
        )
    locator_keys = [
        "adjusted_forecast_vs_py_forecast_yoy",
        "baseline_forecast_vs_py_forecast_yoy",
        "fmi_increment_vs_py_forecast_pp",
        "uplift_fraction",
        "adjusted_forecast",
        "source_q4_sales_yoy_2026",
    ]
    by_key = {r["key"]: r for r in rows}
    return {
        "name": "Column guide",
        "keys": [
            "column",
            "key",
            "header",
            "use",
            "meaning",
            "calculation",
            "source",
            "inputs",
            "type_unit",
            "score_input",
        ],
        "labels": [
            "Delivery column",
            "JSON field key",
            "Delivery header",
            "Delivery use",
            "Detailed meaning / recommended interpretation",
            "Calculation / rule",
            "Source / evidence",
            "Input fields / dependencies",
            "Type / unit",
            "FMI scoring input?",
        ],
        "rows": rows,
        "locators": [by_key[k] for k in locator_keys if k in by_key],
        "period_column": positions.get("forecast_target_label"),
    }
