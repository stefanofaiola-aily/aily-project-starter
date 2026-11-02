"""Human-readable column origins and immediate calculation dependencies."""

from .model import Row

DEPENDENCIES = {
    "raw_fmi": (
        "published_raw_fmi",
        "score_source",
        "score_method",
        "reported_fmi",
        "weighted_component_fmi",
    ),
    "display_fmi": (
        "published_display_fmi",
        "display_fmi_basis",
        "raw_fmi",
        "cohort_min",
        "cohort_max",
        "policy.display_*",
    ),
    "cohort_min": ("included scored rows.raw_fmi",),
    "cohort_max": ("included scored rows.raw_fmi",),
    "uplift_fraction": ("display_fmi", "policy.uplift_*"),
    "adjustment": ("baseline_revenue", "uplift_fraction"),
    "adjusted_forecast": ("baseline_revenue", "adjustment"),
    "legacy_uplift_fraction": ("raw_fmi", "policy.legacy_uplift_*"),
    "legacy_adjustment": ("baseline_revenue", "legacy_uplift_fraction"),
    "legacy_adjusted_forecast": ("baseline_revenue", "legacy_adjustment"),
    "source_legacy_uplift_fraction": ("source_display_fmi", "policy.legacy_uplift_*"),
    "source_legacy_adjusted_forecast": (
        "baseline_revenue",
        "source_legacy_uplift_fraction",
    ),
    "source_projection_difference": (
        "source_legacy_adjusted_forecast",
        "source_projected_forecast",
    ),
    "weighted_component_fmi": (
        "ir_contribution",
        "social_contribution",
        "trend_contribution",
    ),
    "reported_component_difference": (
        "weighted_component_fmi",
        "published_raw_fmi or reported_fmi",
    ),
    "dossier_reported_fmi_difference": ("raw_fmi", "reported_fmi"),
    "raw_classification": ("raw_fmi", "dossier_score_basis"),
    "overall_sentiment": ("raw_fmi",),
    "one_core_insight": (
        "name",
        "raw_fmi",
        "display_fmi",
        "score_method",
        "fmi_status",
    ),
    "fmi_status": ("score_method", "raw_fmi"),
    "forecast_status": (
        "raw_fmi",
        "baseline_revenue",
        "baseline_approved",
        "baseline_kind",
        "baseline_source",
        "baseline_scope",
        "forecast_target_*",
    ),
    "missing_reasons": ("fmi_status", "forecast_status"),
    "prior_year_forecast_comparison_status": (
        "prior_year_forecast_*",
        "forecast_comparison_*",
        "baseline_*",
    ),
    "fmi_increment_vs_py_forecast_pp": (
        "adjusted_forecast_vs_py_forecast_yoy",
        "baseline_forecast_vs_py_forecast_yoy",
    ),
    "policy_version": ("policy.version",),
    "calculation_mode": ("dossier workflow",),
    "historical_eligibility": (
        "dossier snapshot limitations",
        "forecast_vintage_status",
    ),
    "derived_context_fields": ("revenue/growth/gap/social input observations",),
    "has_dossier_data": ("raw_fmi", "components/revenue/social/baseline inputs"),
}
for component, driver in (
    ("ir", "latest_gap_pp"),
    ("social", "social_lift_fraction"),
    ("trend", "latest_growth"),
):
    DEPENDENCIES.update(
        {
            f"{component}_weight": (f"policy.{component}_weight",),
            f"{component}_contribution": (f"{component}_score", f"{component}_weight"),
            f"{component}_status": (f"{component}_score",),
            f"{component}_sentiment": (f"{component}_score",),
            f"{component}_descriptor": (f"{component}_sentiment",),
            f"{component}_insight": (
                driver,
                "financial_period_label"
                if component != "social"
                else "current_start/current_end",
            ),
            f"{component}_kpi": (driver,),
            f"{component}_kpi_label": (
                f"{component}_kpi",
                "component display definition",
            ),
        }
    )
for prefix, amount in (
    ("baseline", "baseline_revenue"),
    ("adjusted", "adjusted_forecast"),
    ("legacy_adjusted", "legacy_adjusted_forecast"),
):
    DEPENDENCIES[f"{prefix}_forecast_yoy"] = (
        amount,
        "prior_year_actual",
        "prior_year_actual_status",
    )
for key, amount in (
    ("baseline_forecast_vs_py_forecast_yoy", "baseline_revenue"),
    ("adjusted_forecast_vs_py_forecast_yoy", "adjusted_forecast"),
    ("legacy_adjusted_forecast_vs_py_forecast_yoy", "legacy_adjusted_forecast"),
    (
        "source_legacy_adjusted_forecast_vs_py_forecast_yoy",
        "source_legacy_adjusted_forecast",
    ),
):
    DEPENDENCIES[key] = (
        amount,
        "prior_year_forecast",
        "prior_year_forecast_comparison_status",
    )
for key in (
    "leaderboard_rank",
    "leaderboard_scored_count",
    "leaderboard_member_count",
    "leaderboard_basis",
    "leaderboard_status",
):
    DEPENDENCIES[key] = (
        "leaderboard_category",
        "delivered rows.display_fmi",
        "include",
        "has_dossier_data",
    )


def field_source(key: str) -> Row:
    """Do not claim dossier values were freshly extracted from a live database."""
    if key.startswith("published_") or key in {
        "score_source",
        "display_fmi_basis",
        "score_context_note",
    }:
        return {
            "source_kind": "published_input_snapshot",
            "source_reference": "FMI_dossier_inputs.xlsx / Inputs; one-time copy of "
            "weighted-delivery-1300.xlsx, the workbook behind existing v6 HTML. "
            "Exact cells in published_source_reference. "
            "Published scores/displays/cards "
            "are preserved independently of dossier alternatives and cohort changes.",
            "source_fields": (key, "published_source_reference"),
        }
    if (
        key
        in {
            "raw_fmi",
            "display_fmi",
            "ir_score",
            "social_score",
            "trend_score",
            "one_core_insight",
        }
        or key.endswith(("_kpi", "_kpi_label", "_descriptor", "_insight", "_sentiment"))
        and not key.startswith("weighted_reference_")
    ):
        return {
            "source_kind": "selected_input",
            "source_reference": "Published input snapshot when score_source is "
            "published_delivery; otherwise selected dossier values/derived context. "
            "published_source_reference or source_document records provenance. "
            "Unselected dossier measurements do not recompute published cards.",
            "source_fields": (
                "score_source",
                "published_" + key,
                "published_card_values",
                *DEPENDENCIES.get(key, (key,)),
            ),
        }
    if key in {
        "leaderboard_category",
        "leaderboard_category_source",
        "leaderboard_category_assignment_status",
        "app_category",
        "in_ranking_company_list",
    }:
        return {
            "source_kind": "input_excel",
            "source_reference": "Current FMI index companies_tuesdaydinner.xlsx "
            "columns A/B; exact category cell in leaderboard_category_source. "
            "Only LUXE/PREMIUM/MASS_MARKET. Unlisted brands have no category/rank.",
            "source_fields": ("company_list column A", "company_list column B"),
        }
    if key.startswith("weighted_reference_"):
        difference = key.endswith("_difference")
        comparison = difference or key in {
            "weighted_reference_match_status",
            "weighted_reference_comparison_reason",
            "weighted_reference_period_status",
        }
        current = key.removeprefix("weighted_reference_").removesuffix("_difference")
        return {
            "source_kind": "comparison" if comparison else "historical_reference",
            "source_reference": "Frozen weighted-reference.json; historical "
            "weighted-delivery workbook and roadmap method metadata. Comparison only.",
            "source_fields": (current, "weighted_reference_" + current)
            if difference
            else ("current scores/periods", "historical reference")
            if comparison
            else ("historical reference",),
        }
    if key == "email_domains":
        return {
            "source_kind": "reviewed_input",
            "source_reference": "Inputs.email_domains; supplied mappings. First "
            "domain is the HTML filename; alternatives remain manifest metadata. "
            "Frozen weighted-delivery domains are a fill-missing fallback only.",
            "source_fields": (key,),
        }
    if (
        key.startswith(("source_q4_", "source_insights_"))
        or key == "source_snapshot_reference"
    ):
        return {
            "source_kind": "historical_snapshot",
            "source_reference": "Frozen weighted-delivery Delivery cells; exact "
            "row in source_snapshot_reference. Sales/social snapshot stays frozen.",
            "source_fields": (key, "source_snapshot_reference"),
        }
    if key in DEPENDENCIES:
        return {
            "source_kind": "derived",
            "source_reference": "Dossier service; immediate dependencies below. "
            "Policy parameters come from scripts/fmi-dossier/policy.yaml.",
            "source_fields": DEPENDENCIES[key],
        }
    if key.startswith(("source_social_", "source_sales_")) or key in {
        "source_display_fmi",
        "source_projected_forecast",
    }:
        origin = (
            "Accepted sales/social workbook transcription; check baseline_source, "
            "forecast_source_notes and source_snapshot_reference."
        )
    elif key == "company_code" or key.startswith(("company_key_", "light_company_")):
        origin = (
            "Saved Light registry check: light.light_companies. company_code is "
            "the app retrieval key; parent/ticker aliases stay separate."
        )
    elif key.startswith("social_") or key in {
        "baseline_median_metric",
        "current_median_metric",
        "baseline_posts",
        "current_posts",
        "baseline_window",
        "current_window",
        "baseline_start",
        "baseline_end",
        "current_start",
        "current_end",
    }:
        origin = (
            "Saved dossier social sample; source_document and social_source "
            "identify the original scanner query. Not a new live shared-DB extraction."
        )
    elif key.startswith(
        ("baseline_", "forecast_", "prior_year_forecast", "prior_year_actual")
    ):
        origin = (
            "Saved accepted forecast/source evidence; inspect baseline_source, "
            "prior_year_forecast_source and forecast_source_notes. Light forecast "
            "relation: ai.light_financial_statements_forecast. No live refresh "
            "during ordinary run."
        )
    elif key in {
        "leaderboard_category",
        "leaderboard_category_source",
        "leaderboard_category_assignment_status",
    }:
        origin = (
            "Current FMI index companies_tuesdaydinner.xlsx column B assignment; "
            "leaderboard_category_source identifies the exact cell. Only LUXE, "
            "PREMIUM and MASS_MARKET are allowed. Unlisted brands have no category."
        )
    elif key in {
        "fmi_required",
        "event_invited",
        "tuesday_dinner_invited",
        "in_ranking_company_list",
        "app_category",
        "light_list_expected",
        "company_list_source",
        "company_list_comment",
    }:
        origin = (
            "Supplied FMI index companies_tuesdaydinner.xlsx / company_list_source."
        )
    else:
        origin = (
            "Dossier transcription or explicit input decision; original document "
            "in source_document, supporting locations in score_evidence, "
            "period_evidence and limitations."
        )
    return {
        "source_kind": "input_excel",
        "source_reference": "FMI_dossier_inputs.xlsx / Inputs, column "
        + key
        + "; match brand_id. "
        + origin,
        "source_fields": (key,),
    }
