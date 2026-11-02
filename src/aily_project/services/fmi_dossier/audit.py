"""Readable score traces from final dossier results; never parse Word or rescore."""

import json
from pathlib import Path

from .model import Row, clean
from .policy import Policy

GROUPS = {
    "Source and selection": (
        "source_document",
        "source_document_original_path",
        "source_score_locator",
        "source_measurement_locators",
        "score_method",
        "dossier_score_basis",
        "score_evidence",
        "include",
        "fmi_required",
        "event_invited",
        "in_ranking_company_list",
        "tuesday_dinner_invited",
        "light_list_expected",
        "light_list_check_status",
        "light_registry_presence",
        "company_list_source",
        "app_category",
        "company_code",
        "company_key_status",
        "company_key_source",
        "company_key_checked_date",
        "collection",
        "show_date",
        "timezone",
        "period_evidence",
        "limitations",
        "historical_eligibility",
    ),
    "Revenue and peers": (
        "financial_subject",
        "scope",
        "currency",
        "unit_multiplier",
        "oldest_revenue",
        "earlier_revenue",
        "latest_revenue",
        "latest_revenue_classification",
        "financial_period_label",
        "financial_period_start",
        "financial_period_end",
        "reference_financial_period_start",
        "reference_financial_period_end",
        "earlier_growth",
        "latest_growth",
        "earlier_peer_median_growth",
        "latest_peer_median_growth",
        "earlier_gap_pp",
        "latest_gap_pp",
        "trend_change_pp",
        "used_peer_names",
        "used_peer_count",
        "peer_observations",
        "derived_context_fields",
    ),
    "Social": (
        "social_platform",
        "social_handle",
        "social_metric",
        "baseline_window",
        "baseline_start",
        "baseline_end",
        "current_window",
        "current_start",
        "current_end",
        "baseline_median_metric",
        "current_median_metric",
        "baseline_posts",
        "current_posts",
        "social_lift_fraction",
        "social_capture_date",
        "social_sample_notes",
        "social_source",
    ),
    "Forecast evidence": (
        "baseline_revenue",
        "baseline_kind",
        "baseline_approved",
        "baseline_source",
        "baseline_subject",
        "baseline_scope",
        "baseline_currency",
        "baseline_unit_multiplier",
        "baseline_company_code",
        "baseline_is_parent_proxy",
        "forecast_baseline_acceptance",
        "forecast_selection_method",
        "forecast_period_start_basis",
        "forecast_native_reported_date",
        "forecast_native_period_label",
        "forecast_native_company_code",
        "forecast_monthly_fallback_status",
        "forecast_target_label",
        "forecast_target_start",
        "forecast_target_end",
        "forecast_vintage",
        "forecast_vintage_status",
        "forecast_source_notes",
        "forecast_lookup_status",
        "forecast_lookup_extracted_at",
        "forecast_lookup_company_candidates",
        "forecast_lookup_candidates",
        "prior_year_actual",
        "prior_year_actual_status",
        "prior_year_actual_period_end",
        "prior_year_forecast",
        "prior_year_forecast_status",
        "prior_year_forecast_source",
        "prior_year_forecast_source_row_id",
        "prior_year_forecast_extracted_at",
        "prior_year_forecast_reported_date",
        "prior_year_forecast_vintage",
        "prior_year_forecast_native_period_label",
        "prior_year_forecast_notes",
        "forecast_comparison_native_period_label",
        "forecast_comparison_baseline_revenue",
    ),
    "Results": (
        "reported_fmi",
        "ir_score",
        "ir_status",
        "ir_weight",
        "ir_contribution",
        "social_score",
        "social_status",
        "social_weight",
        "social_contribution",
        "trend_score",
        "trend_status",
        "trend_weight",
        "trend_contribution",
        "weighted_component_fmi",
        "reported_component_difference",
        "raw_fmi",
        "raw_classification",
        "fmi_status",
        "display_fmi",
        "cohort_min",
        "cohort_max",
        "policy_version",
        "uplift_fraction",
        "adjustment",
        "adjusted_forecast",
        "legacy_uplift_fraction",
        "legacy_adjustment",
        "legacy_adjusted_forecast",
        "source_display_fmi",
        "source_legacy_uplift_fraction",
        "source_projected_forecast",
        "source_legacy_adjusted_forecast",
        "source_projection_difference",
        "baseline_forecast_yoy",
        "adjusted_forecast_yoy",
        "legacy_adjusted_forecast_yoy",
        "baseline_forecast_vs_py_forecast_yoy",
        "adjusted_forecast_vs_py_forecast_yoy",
        "legacy_adjusted_forecast_vs_py_forecast_yoy",
        "fmi_increment_vs_py_forecast_pp",
        "prior_year_forecast_comparison_status",
        "forecast_status",
        "missing_reasons",
        "leaderboard_category",
        "leaderboard_rank",
        "leaderboard_status",
    ),
    "Frozen historical delivery snapshot": (
        "source_snapshot_reference",
        "email_domains",
        "source_social_2024",
        "source_social_2025",
        "source_social_2026",
        "source_q4_vs_baseline_2024",
        "source_q4_vs_baseline_2025",
        "source_q4_vs_baseline_2026",
        "source_q4_sales_yoy_2024",
        "source_q4_sales_yoy_2025",
        "source_q4_sales_yoy_2026",
        "source_insights_descriptive",
        "source_insights_statistics",
    ),
}


def traces(rows: list[Row]) -> list[Row]:
    """Include excluded and missing prospects, without manufacturing source detail."""
    return clean(
        [
            {
                "brand_id": r["brand_id"],
                "name": r["name"],
                "component_origin": (
                    "Dossier transcription, not independent recalculation"
                ),
                "groups": {
                    name: {key: r.get(key) for key in keys}
                    for name, keys in GROUPS.items()
                },
            }
            for r in rows
        ]
    )


def display(value: object) -> str:
    if value is None:
        return "missing"
    if isinstance(value, (list, dict)):
        text = json.dumps(value, ensure_ascii=False, allow_nan=False)
    elif isinstance(value, float):
        text = format(value, ".12g")
    else:
        text = str(value)
    return text.replace("|", "\\|").replace("\n", "<br>")


def write_audit(records: list[Row], cohort: Row, policy: Policy, output: Path) -> None:
    """One human-readable file, using exactly the values delivered by the service."""
    lines = [
        "# Dossier calculation audit",
        "",
        "This file covers every input prospect, including missing/excluded results. "
        "Component scores and printed headlines are transcribed from dossiers, not "
        "independently rebuilt from database measurements. Missing source locators or "
        "sample counts remain missing. Printed growth and lift take precedence over "
        "calculations from rounded amounts. `derived_context_fields` identifies "
        "context "
        "calculated by the service; it does not change a reported headline.",
        "",
        "Rates/growth are fractions; gaps/change are percentage points; "
        "scores are 0–100. "
        "Amounts use each row's currency and unit multiplier. Missing is not zero.",
        "",
        "## Resolved policy and cohort",
        "",
        "```json",
        json.dumps(clean({"policy": policy.model_dump(), "cohort": cohort}), indent=2),
        "```",
        "",
        "Dynamic cohort normalization can change an unchanged brand's uplift. "
        "The approved exponential is calibrated on the legacy raw-score scale but "
        "applied to rounded normalized FMI. Default scores 70–98 give about "
        "5.27–15.69% uplift; score 100 gives 16.75%. There is no 11% cap. "
        "Uplifts are business scenarios, not calibrated predictions or verified "
        "historical replay.",
        "",
    ]
    for record in records:
        groups = record["groups"]
        r = {k: v for fields in groups.values() for k, v in fields.items()}
        v = {k: display(value) for k, value in r.items()}.__getitem__
        lines.extend([f"## {record['name']} ({record['brand_id']})", ""])
        for name, fields in groups.items():
            lines.extend([f"### {name}", "", "| Field | Value |", "| --- | --- |"])
            lines.extend(f"| `{k}` | {display(value)} |" for k, value in fields.items())
            lines.append("")
        selection = (
            "Selected raw FMI preserves the printed dossier headline"
            if r.get("score_method") == "reported"
            else "Selected raw FMI uses the explicit weighted-components method"
        )
        lines.extend(
            [
                "### Calculation steps",
                "",
                f"1. Weighted diagnostic: {v('ir_score')} × {v('ir_weight')} + "
                f"{v('social_score')} × {v('social_weight')} + "
                f"{v('trend_score')} × {v('trend_weight')} = "
                f"{v('weighted_component_fmi')}. "
                "A missing component makes this diagnostic unavailable.",
                f"2. {selection}: {v('raw_fmi')}. Diagnostic minus printed headline = "
                f"{v('reported_component_difference')}; "
                "the diagnostic never silently replaces it.",
                f"3. Display: half-up to one decimal of {policy.display_lower:g} + "
                f"({policy.display_upper:g} − {policy.display_lower:g}) × "
                f"({v('raw_fmi')} − {v('cohort_min')}) / "
                f"({v('cohort_max')} − {v('cohort_min')}) = {v('display_fmi')}. "
                f"Equal/single cohorts use {policy.display_equal:g}; "
                "missing/excluded scores stay missing.",
                f"4. Legacy rate: 0 if raw ≤ {policy.legacy_uplift_threshold:g}; "
                "otherwise "
                f"{policy.legacy_uplift_intercept:g} + "
                f"(raw − {policy.legacy_uplift_threshold:g}) × "
                f"{policy.legacy_uplift_per_score:g}. "
                f"Rate = {v('legacy_uplift_fraction')}; "
                f"adjustment = {v('baseline_revenue')} × {v('legacy_uplift_fraction')} "
                f"= {v('legacy_adjustment')}; "
                f"adjusted = {v('legacy_adjusted_forecast')}.",
                f"5. Exponential rate: 0 if display ≤{policy.uplift_threshold:g}; "
                f"otherwise {policy.uplift_intercept:g} + {policy.uplift_scale:g} × "
                f"expm1({policy.uplift_exponent:g} × "
                f"({v('display_fmi')} − {policy.uplift_threshold:g}) / "
                f"{policy.uplift_score_span:g}) = {v('uplift_fraction')}; "
                f"adjustment = {v('baseline_revenue')} × {v('uplift_fraction')} "
                f"= {v('adjustment')}; "
                f"baseline + adjustment = {v('adjusted_forecast')}. "
                f"Baseline eligibility: {v('forecast_status')}.",
                "6. Source legacy reproduction uses the original `source_display_fmi`, "
                "not the current raw/display score. YoY comparisons use matching "
                "amount / prior-year amount − 1; "
                "actuals and PY forecasts remain distinct. "
                "Missing or incompatible denominators do not produce a YoY.",
                "",
            ]
        )
    (output / "calculation-audit.md").write_text("\n".join(lines) + "\n")
