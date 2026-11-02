"""Versioned app field dictionary; stable keys and explicit measurement units."""

from dataclasses import dataclass

from .models import Row, calendar_date, instant, number


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    group: str
    type: str = "string"
    unit: str = "text"
    description: str = ""
    derivation: str = "reviewed source or input"
    required: bool = False
    influences_fmi: bool = False

    def record(self) -> Row:
        return {
            "field_key": self.key,
            "excel_label": self.label,
            "group": self.group,
            "description": self.description or self.label,
            "type": self.type,
            "unit": self.unit,
            "derivation": self.derivation,
            "required": self.required,
            "influences_fmi": self.influences_fmi,
        }


def dictionary() -> list[Field]:
    result = []

    def add(
        keys: str,
        group: str,
        type_: str = "string",
        unit: str = "text",
        derivation: str = "reviewed source or input",
        required: bool = False,
        influences: bool = False,
    ) -> None:
        for key in keys.split():
            result.append(
                Field(
                    key,
                    key.replace("_", " ").capitalize(),
                    group,
                    type_,
                    unit,
                    derivation=derivation,
                    required=required,
                    influences_fmi=influences,
                )
            )

    add("brand_id analysis_id name", "Headline", required=True)
    add(
        "dossier_source dossier_parameter_status",
        "Analysis",
        derivation="Editable dossier business parameters and linked report",
    )
    add(
        "headline_method dossier_score_basis dossier_headline_replication_status",
        "Analysis",
        derivation="Current weighted headline method and separate frozen dossier "
        "normalization basis. Weighted components do not replicate historical "
        "percentiles.",
    )
    add(
        "social_used_members social_member_missing_reasons",
        "Social",
        derivation="Dossier portfolio members used/excluded; one lift per member",
    )
    add(
        "trend_basis trend_comparison",
        "Trend",
        derivation="Dossier peer gap, company growth or labelled assumption",
        influences=True,
    )
    add(
        "social_scoring_metric",
        "Social",
        derivation="Dossier metric; likes by default, explicitly selected comments",
        influences=True,
    )
    add(
        "financial_currency_status",
        "Quality",
        derivation="Source currency takes precedence. Missing source currency may "
        "use registry denomination in presentation only: assumption, not verification.",
    )
    add(
        "baseline_currency_basis",
        "Forecast",
        derivation="Source currency, consistent same-subject actual-source currency "
        "assumption, or registry denomination assumption. Never FX conversion or "
        "verified forecast reporting currency without source evidence.",
    )
    add(
        "parent_name parent_mapping_evidence parent_fallback_status "
        "used_peer_financial_subjects social_month_selection",
        "Mapping and selection",
        derivation="Evidenced presentation parent fallback and actual peer subjects. "
        "Parent amounts are NOT standalone brand amounts; common months are explicit.",
    )
    add(
        "raw_fmi display_fmi",
        "Headline",
        "number",
        "score_0_100",
        "weighted score; display uses available selected cohort in declared mode",
        influences=True,
    )
    add("raw_classification fmi_status forecast_status", "Headline")
    add(
        "calculation_mode release_status",
        "Headline",
        derivation="Current-source simulation, never reviewed historical replay",
    )
    add(
        "scenario_as_of signal_window_cutoff",
        "Analysis",
        "datetime",
        "UTC",
        "Current snapshot time and original document-derived signal cutoff",
    )
    add(
        "scenario_quarter_tolerance_days scenario_forecast_tolerance_days",
        "Analysis",
        "integer",
        "days",
        "Maximum YoY end-date drift / selected forecast distance from requested target",
    )
    add(
        "revenue_alignment_status financial_selection_basis financial_unit_status "
        "financial_scope_status social_selection_basis baseline_validation_status",
        "Quality",
        derivation="Simulation selection and unverified scope/scale/vintage",
    )
    add(
        "used_peer_count",
        "Peer comparison",
        "integer",
        "count",
        "Assigned peers with both comparable growth measurements; not approval",
    )
    add(
        "used_peer_names peer_exclusion_reasons",
        "Peer comparison",
        derivation="Same usable assigned subset; excluded peers and reasons",
    )
    add(
        "baseline_period_start",
        "Forecast",
        "date",
        "calendar_date",
        "Native quarter proxy boundaries; not verified source boundaries",
    )
    add("baseline_source_row_id baseline_source_relation baseline_currency", "Forecast")
    add(
        "baseline_period_label baseline_native_quarter",
        "Headline",
        derivation="Selected forecast's original fiscal/retail source label, "
        "not requested calendar label",
    )
    add("baseline_period_end", "Headline", "date", "calendar_date")
    add("baseline_fiscal_year", "Forecast", "integer", "source_fiscal_year")
    add(
        "forecast_selection_basis forecast_calendar_alignment_status "
        "prior_year_actual_status",
        "Forecast",
        derivation="Requested calendar target versus actual native forecast "
        "and matching YoY actual",
    )
    add("forecast_target_end_difference_days", "Forecast", "integer", "days")
    add("prior_year_actual_period_label", "Forecast")
    add("prior_year_actual_period_end", "Forecast", "date", "calendar_date")
    add("financial_basis financial_freshness_status", "Revenue")
    add(
        "latest_actual_age_days",
        "Revenue",
        "integer",
        "days",
        "Snapshot date minus latest actual end; over 180 days is flagged, not excluded",
    )
    add(
        "used_peer_periods peer_calendar_alignment_status",
        "Peer comparison",
        derivation="Each used peer's native labels/end dates; "
        "different dates are explicitly disclosed",
    )
    add(
        "baseline_unit_multiplier",
        "Forecast",
        "number",
        "currency_units_per_stored_unit",
        "Unknown native source scale stays null; uplift preserves native amount",
    )
    add(
        "uplift_fraction",
        "Headline",
        "number",
        "fraction",
        "uplift_max * expm1(exponent * rounded display / 100) / expm1(exponent)",
    )
    add(
        "baseline_revenue adjustment adjusted_forecast",
        "Headline",
        "number",
        "currency_times_unit_multiplier",
        "eligible baseline; adjustment = baseline * uplift; "
        "adjusted = baseline + adjustment",
    )
    add(
        "legacy_uplift_fraction",
        "Headline",
        "number",
        "fraction",
        "0 if unrounded raw FMI <= threshold; otherwise intercept "
        "+ (raw FMI - threshold) * per-score slope",
    )
    add(
        "legacy_adjustment legacy_adjusted_forecast",
        "Headline",
        "number",
        "currency_times_unit_multiplier",
        "Same eligible baseline as new method, multiplied by legacy raw-score uplift",
    )
    add("legacy_uplift_score_basis uplift_score_basis", "Forecast")
    add(
        "legacy_adjusted_forecast_yoy",
        "Forecast",
        "number",
        "fraction",
        "legacy adjusted forecast / compatible prior-year actual - 1",
    )
    add("event_category", "Event")
    add("event_invited fmi_required", "Event", "boolean", "boolean")
    add(
        "data_extracted_at",
        "Quality",
        "datetime",
        "UTC",
        "Authenticated snapshot extraction time; not a historical measurement vintage",
    )
    add(
        "financial_candidate_count social_capture_count",
        "Quality",
        "integer",
        "count",
        "Source candidate/capture row counts, not eligible sample counts",
    )
    add("source_query_coverage_status", "Quality")
    add(
        "entity_id light_code ticker shared_symbol financial_subject scope "
        "proxy_label handle profile_id social_platform",
        "Identity",
    )
    add("proxy", "Identity", "boolean", "boolean")
    add("route collection timezone forecast_target_label", "Analysis")
    add(
        "show_date forecast_target_start forecast_target_end",
        "Analysis",
        "date",
        "calendar_date",
    )
    add(
        "cutoff",
        "Analysis",
        "datetime",
        "UTC",
        "end of local show date +37; annual explicit cutoff",
    )
    add("headline_selection", "Analysis", "boolean", "boolean")
    add("policy_id policy_hash run_id cohort_id", "Analysis")
    add(
        "cohort_min cohort_max",
        "Analysis",
        "number",
        "score_0_100",
        "reviewed selected headline extrema",
    )
    add("cohort_count", "Analysis", "integer", "count")
    add(
        "ir_score social_score trend_score",
        "FMI",
        "number",
        "score_0_100",
        "IR=clip(50+5*gap); Social=clip(50+100*likes_lift); ordered Trend rules",
        influences=True,
    )
    add(
        "ir_weight social_weight trend_weight",
        "FMI",
        "number",
        "fraction",
        "resolved policy",
        influences=True,
    )
    add(
        "ir_contribution social_contribution trend_contribution",
        "FMI",
        "number",
        "score_points",
        "component score * corresponding weight",
        influences=True,
    )
    add("currency", "Revenue")
    add("unit_multiplier", "Revenue", "number", "currency_units_per_stored_unit")
    for role in ("oldest", "earlier", "latest"):
        add(
            f"{role}_revenue",
            "Revenue",
            "number",
            "currency_times_unit_multiplier",
            influences=True,
        )
        add(f"{role}_period_label {role}_source_classification", "Revenue")
        add(
            f"{role}_source_row_id {role}_source_relation {role}_source_url",
            "Revenue",
            derivation="Selected source ID, database relation and issuer URL",
        )
        add(f"{role}_currency", "Revenue")
        add(
            f"{role}_unit_multiplier",
            "Revenue",
            "number",
            "currency_units_per_stored_unit",
        )
        add(
            f"{role}_period_start {role}_period_end", "Revenue", "date", "calendar_date"
        )
    add(
        "earlier_growth latest_growth earlier_peer_median_growth "
        "latest_peer_median_growth",
        "Peers",
        "number",
        "fraction",
        "current/prior-1; median of the same approved peer set",
        influences=True,
    )
    add(
        "earlier_gap_pp latest_gap_pp",
        "Peers",
        "number",
        "pp",
        "100 * (brand growth - peer median growth)",
        influences=True,
    )
    add("approved_peer_names comparability_status", "Peers")
    add("approved_peer_count", "Peers", "integer", "count")
    add(
        "trend_change_pp",
        "Trend",
        "number",
        "pp",
        "latest_gap_pp - earlier_gap_pp",
        influences=True,
    )
    add("trend_label", "Trend")
    add(
        "current_window baseline_window relevance_review_status social_coverage_status",
        "Social",
    )
    for sample in ("current", "baseline"):
        add(
            " ".join(
                f"{sample}_{k}_posts"
                for k in ("total", "usable", "included", "excluded")
            ),
            "Social",
            "integer",
            "posts",
            "retained eligible captures and reviewed sample membership",
        )
        add(
            f"{sample}_median_likes",
            "Social",
            "number",
            "likes_per_post",
            "median of usable reviewed posts",
            influences=True,
        )
        add(
            f"{sample}_usable_likes",
            "Social",
            "integer",
            "posts",
            "posts with nonmissing nonnegative likes",
            influences=True,
        )
        for metric in ("comments", "views"):
            add(
                f"{sample}_median_{metric}",
                "Social context",
                "number",
                f"{metric}_per_post",
                "median of available reviewed sample observations; "
                "partial sample, not a complete total",
            )
            add(
                f"{sample}_usable_{metric}",
                "Social context",
                "integer",
                "posts",
                f"denominator for {metric} median",
            )
        add(
            " ".join(
                f"{sample}_{f}_posts"
                for f in (
                    "image",
                    "video",
                    "carousel",
                    "unknown",
                    "other_format",
                    "paid_true",
                    "paid_false",
                    "paid_unknown",
                )
            ),
            "Social context",
            "integer",
            "posts",
            "counts in reviewed sample; missing likes need not exclude context",
        )
    add(
        "likes_lift",
        "Social",
        "number",
        "fraction",
        "current median likes / baseline median likes - 1",
        influences=True,
    )
    add(
        "comments_lift views_lift follower_growth",
        "Social context",
        "number",
        "fraction",
        "current / comparable prior - 1; positive prior denominator required",
    )
    add(
        "common_months",
        "Social",
        "integer",
        "months",
        "intersection of usable annual sample months",
    )
    add(
        "follower_count prior_follower_count",
        "Social context",
        "number",
        "followers",
        "eligible captures of the same approved profile",
    )
    add("follower_capture prior_follower_capture", "Social context", "datetime", "UTC")
    for role in ("oldest", "earlier", "latest"):
        for metric in ("cost_of_revenue", "gross_profit", "ebitda"):
            add(
                f"{role}_{metric}",
                "Financial context",
                "number",
                "currency_times_unit_multiplier",
                "independently selected verified scope-compatible observation",
            )
            add(
                f"{role}_{metric}_margin",
                "Financial context",
                "number",
                "fraction",
                "context amount / same-period revenue",
            )
    add(
        "forecast_vintage",
        "Forecast",
        "datetime",
        "UTC",
        "verified forecast available_at",
    )
    add("prior_year_actual", "Forecast", "number", "currency_times_unit_multiplier")
    add(
        "baseline_forecast_yoy adjusted_forecast_yoy",
        "Forecast",
        "number",
        "fraction",
        "forecast / compatible prior-year actual - 1",
    )
    add(
        "ir_status social_status trend_status forecast_missing_reason "
        "historical_status missing_reasons evidence_refs narrative",
        "Quality",
    )
    add(
        "identity_status analysis_review_status financial_coverage_status "
        "peer_review_status social_history_status forecast_vintage_status",
        "Quality",
    )
    return result


FIELDS = dictionary()


def canonical_record(record: Row) -> Row:
    unknown = set(record) - {f.key for f in FIELDS}
    if unknown:
        raise ValueError(f"Fields missing from app contract: {sorted(unknown)}")
    result = {}
    for f in FIELDS:
        value = record.get(f.key)
        if value is not None:
            if f.type in ("number", "integer"):
                value = number(value)
                if value is None or (f.type == "integer" and value != int(value)):
                    raise ValueError(f"Invalid {f.type} app field: {f.key}")
                if f.type == "integer":
                    value = int(value)
            elif f.type == "boolean":
                if not isinstance(value, bool):
                    raise ValueError(f"Invalid boolean app field: {f.key}")
            elif f.type == "date":
                value = calendar_date(value).isoformat()
            elif f.type == "datetime":
                timestamp = instant(value)
                if timestamp is None:
                    raise ValueError(f"Timezone-qualified timestamp required: {f.key}")
                value = timestamp.isoformat()
            else:
                value = str(value)
        result[f.key] = value
    return result
