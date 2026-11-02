"""Dossier Excel inputs → score → delivery. No document parser or cloud reads."""

import json
import math
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

from .audit import traces, write_audit
from .model import Field, Row, clean, truth
from .policy import Policy, classify, half_up, legacy_uplift, uplift
from .presentation import enrich, leaderboards, rank_categories, save_handoff
from .workbook import write_workbook

# The input is a flat table, not a second configuration/review system.
NUMBERS = set(
    [
        "reported_fmi",
        "source_original_fmi",
        "source_display_fmi",
        "ir_score",
        "social_score",
        "trend_score",
        "oldest_revenue",
        "earlier_revenue",
        "latest_revenue",
        "unit_multiplier",
        "earlier_growth",
        "latest_growth",
        "earlier_peer_median_growth",
        "latest_peer_median_growth",
        "earlier_gap_pp",
        "latest_gap_pp",
        "trend_change_pp",
        "baseline_median_metric",
        "current_median_metric",
        "baseline_posts",
        "current_posts",
        "social_lift_fraction",
        "baseline_revenue",
        "source_projected_forecast",
        "prior_year_actual",
        "source_sales_2023",
        "source_sales_2024",
        "source_sales_2025",
        "source_social_2024",
        "source_social_2025",
        "source_social_2026",
        "baseline_unit_multiplier",
        "weighted_component_fmi",
        "reported_component_difference",
        "raw_fmi",
        "display_fmi",
        "cohort_min",
        "cohort_max",
        "ir_weight",
        "social_weight",
        "trend_weight",
        "ir_contribution",
        "social_contribution",
        "trend_contribution",
        "uplift_fraction",
        "adjustment",
        "adjusted_forecast",
        "legacy_uplift_fraction",
        "legacy_adjustment",
        "legacy_adjusted_forecast",
        "baseline_forecast_yoy",
        "adjusted_forecast_yoy",
        "legacy_adjusted_forecast_yoy",
        "used_peer_count",
        "forecast_candidate_revenue",
        "source_legacy_uplift_fraction",
        "source_legacy_adjusted_forecast",
        "source_projection_difference",
        "forecast_native_unit_multiplier",
        "forecast_candidate_unit_multiplier",
        "forecast_candidate_baseline_revenue",
    ]
)
NUMBERS |= {
    "weighted_reference_" + key
    for key in (
        "raw_fmi",
        "display_fmi",
        "ir_score",
        "social_score",
        "trend_score",
        "raw_fmi_difference",
        "ir_score_difference",
        "social_score_difference",
        "trend_score_difference",
    )
}
PY_YOY = {
    "baseline_forecast_vs_py_forecast_yoy": "baseline_revenue",
    "adjusted_forecast_vs_py_forecast_yoy": "adjusted_forecast",
    "legacy_adjusted_forecast_vs_py_forecast_yoy": "legacy_adjusted_forecast",
    "source_legacy_adjusted_forecast_vs_py_forecast_yoy": (
        "source_legacy_adjusted_forecast"
    ),
}
NUMBERS |= set(PY_YOY) | {
    "prior_year_forecast",
    "prior_year_forecast_unit_multiplier",
    "prior_year_forecast_native_amount",
    "prior_year_forecast_native_unit_multiplier",
    "prior_year_forecast_native_year",
    "forecast_comparison_native_year",
    "forecast_comparison_baseline_revenue",
    "fmi_increment_vs_py_forecast_pp",
    "leaderboard_rank",
    "leaderboard_scored_count",
    "leaderboard_member_count",
}
LABELS = {
    "raw_fmi": "Fashion Momentum Index (dossier)",
    "display_fmi": "FMI normalized (70–98)",
    "ir_score": "Trend / Peer Trajectory (IR)",
    "social_score": "Social / Show Attention",
    "trend_score": "Revenue / Commercial Pace (Strength)",
    "uplift_fraction": "Exponential uplift rate",
    "adjusted_forecast": "Exponential adjusted forecast",
    "legacy_uplift_fraction": "Legacy uplift rate (raw FMI)",
    "legacy_adjusted_forecast": "Legacy adjusted forecast (raw FMI)",
    "source_legacy_uplift_fraction": "Source legacy uplift rate (source display)",
    "source_legacy_adjusted_forecast": "Source legacy reproduced forecast",
    "source_projection_difference": "Reproduced minus source forecast",
    "baseline_forecast_yoy": "Baseline forecast YoY vs PY actual",
    "adjusted_forecast_yoy": "Exponential forecast YoY vs PY actual",
    "legacy_adjusted_forecast_yoy": "Legacy forecast YoY vs PY actual",
    "prior_year_forecast": "PY forecast (current Light snapshot)",
    "baseline_forecast_vs_py_forecast_yoy": "Baseline forecast YoY vs PY forecast",
    "adjusted_forecast_vs_py_forecast_yoy": "Exponential forecast YoY vs PY forecast",
    "legacy_adjusted_forecast_vs_py_forecast_yoy": "Legacy forecast YoY vs PY forecast",
    "source_legacy_adjusted_forecast_vs_py_forecast_yoy": (
        "Source legacy forecast YoY vs PY forecast"
    ),
    "fmi_increment_vs_py_forecast_pp": "Exponential FMI incremental YoY (pp)",
    "leaderboard_category": "Leaderboard category",
    "leaderboard_rank": "Category rank (provisional)",
    "weighted_reference_raw_fmi": "Historical weighted FMI",
    "weighted_reference_display_fmi": "Historical normalized FMI",
    "weighted_reference_ir_score": "Historical IR score",
    "weighted_reference_social_score": "Historical Social score",
    "weighted_reference_trend_score": "Historical Strength score",
}
DATES = set(
    [
        "show_date",
        "financial_period_start",
        "financial_period_end",
        "reference_financial_period_start",
        "reference_financial_period_end",
        "current_start",
        "current_end",
        "baseline_start",
        "baseline_end",
        "social_capture_date",
        "forecast_target_start",
        "forecast_target_end",
        "forecast_vintage",
        "prior_year_actual_period_end",
        "company_key_verified_date",
        "company_key_checked_date",
        "forecast_baseline_checked_date",
    ]
)
DATES |= {
    "forecast_native_reported_date",
    "prior_year_forecast_reported_date",
    "forecast_comparison_reported_date",
    "prior_year_forecast_target_start",
    "prior_year_forecast_target_end",
    "prior_year_forecast_vintage",
}
FLAGS = {
    "in_ranking_company_list",
    "tuesday_dinner_invited",
    "baseline_is_parent_proxy",
    "include",
    "fmi_required",
    "event_invited",
    "baseline_approved",
    "has_dossier_data",
    "app_content_approved",
}
FRACTIONS = {k for k in NUMBERS if k.endswith("_growth") or k.endswith("_yoy")}
FRACTIONS |= {
    "social_lift_fraction",
    "uplift_fraction",
    "legacy_uplift_fraction",
    "source_legacy_uplift_fraction",
    "ir_weight",
    "social_weight",
    "trend_weight",
    "source_social_2024",
    "source_social_2025",
    "source_social_2026",
}
FRACTIONS |= set(PY_YOY)
LOOKUP_ARRAYS = {"forecast_lookup_candidates", "forecast_lookup_company_candidates"}
LOOKUP_DATES = {"forecast_lookup_target_start", "forecast_lookup_target_end"}
HEADLINE = [
    "brand_id",
    "name",
    "company_code",
    "fmi_required",
    "event_invited",
    "raw_fmi",
    "display_fmi",
    "leaderboard_category",
    "leaderboard_rank",
    "leaderboard_scored_count",
    "uplift_fraction",
    "adjusted_forecast",
    "legacy_uplift_fraction",
    "legacy_adjusted_forecast",
    "baseline_is_parent_proxy",
    "baseline_subject",
    "baseline_currency",
    "forecast_target_label",
    "prior_year_forecast",
    "baseline_forecast_vs_py_forecast_yoy",
    "adjusted_forecast_vs_py_forecast_yoy",
    "legacy_adjusted_forecast_vs_py_forecast_yoy",
    "fmi_increment_vs_py_forecast_pp",
    "prior_year_forecast_comparison_status",
    "source_legacy_uplift_fraction",
    "source_legacy_adjusted_forecast",
    "source_projection_difference",
    "fmi_status",
    "forecast_status",
    "score_method",
    "dossier_score_basis",
    "ir_score",
    "social_score",
    "trend_score",
    "overall_sentiment",
    "one_core_insight",
    "ir_descriptor",
    "ir_insight",
    "ir_kpi",
    "ir_kpi_label",
    "social_descriptor",
    "social_insight",
    "social_kpi",
    "social_kpi_label",
    "trend_descriptor",
    "trend_insight",
    "trend_kpi",
    "trend_kpi_label",
    "weighted_reference_match_status",
    "weighted_reference_raw_fmi",
    "weighted_reference_display_fmi",
    "weighted_reference_ir_score",
    "weighted_reference_social_score",
    "weighted_reference_trend_score",
    "weighted_reference_comparison_reason",
]


def read_excel(path: Path) -> list[Row]:
    """Read editable values. Reject formulas, duplicate IDs and invalid metrics."""
    workbook = load_workbook(path, read_only=True, data_only=False)
    try:
        sheet = workbook["Inputs"]
        iterator = iter(sheet.values)
        keys = next(iterator)
        if len(keys) != len(set(keys)) or any(not isinstance(k, str) for k in keys):
            raise ValueError("Inputs needs unique nonblank field keys in row 1")
        required = {"brand_id", "name", "source_document", "score_method"}
        if not required <= set(keys):
            raise ValueError(
                "Missing input columns: " + ", ".join(sorted(required - set(keys)))
            )
        rows, ids = [], set()
        for index, values in enumerate(iterator, 2):
            if not any(v is not None for v in values):
                continue
            row = dict(zip(keys, values, strict=True))
            if not row["brand_id"] or row["brand_id"] in ids:
                raise ValueError(f"Row {index}: blank or duplicate brand_id")
            ids.add(row["brand_id"])
            for key, value in row.items():
                if isinstance(value, str) and value.startswith("="):
                    raise ValueError(
                        f"Row {index}, {key}: enter a value, not a formula"
                    )
                # The workbook writer escapes source strings that resemble formulas.
                if (
                    isinstance(value, str)
                    and value.startswith("'")
                    and value[1:].startswith(("=", "+", "-", "@"))
                ):
                    value = value[1:]
                    row[key] = value
                if (
                    key in NUMBERS
                    and value is not None
                    and (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(value)
                    )
                ):
                    raise ValueError(
                        f"Row {index}, {key}: enter a finite number or leave blank"
                    )
                if key in DATES and value is not None:
                    row[key] = (
                        (
                            value.date() if isinstance(value, datetime) else value
                        ).isoformat()
                        if isinstance(value, date)
                        else date.fromisoformat(str(value)).isoformat()
                    )
                if key in FLAGS:
                    if value not in (
                        None,
                        True,
                        False,
                        "true",
                        "false",
                        "TRUE",
                        "FALSE",
                    ):
                        raise ValueError(f"Row {index}, {key}: use TRUE or FALSE")
                    row[key] = truth(value)
            rows.append(row)
        return rows
    finally:
        workbook.close()


def score_rows(inputs: list[Row], policy: Policy) -> list[Row]:
    """Preserve report headlines; offer an explicit weighted-component mode."""
    rows = []
    for source in inputs:
        row = dict(source)
        # Derive descriptive metrics only when the dossier supplies comparable
        # source amounts. Existing printed measurements always take precedence.
        derived = []
        for output, current, prior in (
            ("earlier_growth", "earlier_revenue", "oldest_revenue"),
            ("latest_growth", "latest_revenue", "earlier_revenue"),
            ("social_lift_fraction", "current_median_metric", "baseline_median_metric"),
        ):
            a, b = row.get(current), row.get(prior)
            if row.get(output) is None and a is not None and b is not None and b > 0:
                if "revenue" in current and not all(
                    row.get(k) for k in ("scope", "currency", "unit_multiplier")
                ):
                    continue
                row[output] = a / b - 1
                derived.append(output)
        for output, growth, peer in (
            ("earlier_gap_pp", "earlier_growth", "earlier_peer_median_growth"),
            ("latest_gap_pp", "latest_growth", "latest_peer_median_growth"),
        ):
            if (
                row.get(output) is None
                and row.get(growth) is not None
                and row.get(peer) is not None
            ):
                row[output] = 100 * (row[growth] - row[peer])
                derived.append(output)
        if (
            row.get("trend_change_pp") is None
            and row.get("latest_gap_pp") is not None
            and row.get("earlier_gap_pp") is not None
        ):
            row["trend_change_pp"] = row["latest_gap_pp"] - row["earlier_gap_pp"]
            derived.append("trend_change_pp")
        row["derived_context_fields"] = ", ".join(derived) or None
        peers = row.get("peer_observations")
        if isinstance(peers, str):
            peers = json.loads(peers)
        if peers is not None and not isinstance(peers, list):
            raise ValueError(
                f"{row['brand_id']}: peer_observations must be a JSON list"
            )
        row["peer_observations"] = peers
        for key in LOOKUP_ARRAYS:
            value = row.get(key)
            if isinstance(value, str):
                value = json.loads(value)
            if value is not None and (
                not isinstance(value, list)
                or any(not isinstance(item, dict) for item in value)
            ):
                raise ValueError(
                    f"{row['brand_id']}: {key} must be source-record arrays"
                )
            if key in row:
                row[key] = value
        method = row.get("score_method")
        if method not in {"reported", "weighted_components"}:
            raise ValueError(
                f"{row['brand_id']}: score_method must be reported "
                "or weighted_components"
            )
        for key in ("reported_fmi", "ir_score", "social_score", "trend_score"):
            if row.get(key) is not None and not 0 <= row[key] <= 100:
                raise ValueError(f"{row['brand_id']}: {key} must be in 0–100")
        for component in ("ir", "social", "trend"):
            value = row.get(component + "_score")
            weight = getattr(policy, component + "_weight")
            row[component + "_weight"] = weight
            row[component + "_contribution"] = (
                value * weight if value is not None else None
            )
            row[component + "_status"] = (
                "available" if value is not None else "missing_dossier_component"
            )
        contributions = [row[c + "_contribution"] for c in ("ir", "social", "trend")]
        weighted = (
            sum(contributions) if all(v is not None for v in contributions) else None
        )
        row["weighted_component_fmi"] = weighted
        reported = row.get("reported_fmi")
        row["reported_component_difference"] = (
            weighted - reported
            if weighted is not None and reported is not None
            else None
        )
        raw = reported if method == "reported" else weighted
        if raw is not None and not row.get("source_document"):
            raise ValueError(f"{row['brand_id']}: a score needs a source_document")
        row["raw_fmi"] = raw
        row["has_dossier_data"] = any(
            row.get(k) is not None
            for k in (
                "raw_fmi",
                "ir_score",
                "social_score",
                "trend_score",
                "latest_revenue",
                "current_median_metric",
                "baseline_revenue",
                "source_sales_2025",
                "source_social_2026",
            )
        )
        row["raw_classification"] = (
            classify(raw)
            if raw is not None
            and row.get("dossier_score_basis") != "component_percentile_normalized"
            else None
        )
        row["fmi_status"] = (
            "available"
            if raw is not None
            else "missing_dossier_headline"
            if method == "reported"
            else "missing_dossier_components"
        )
        row["calculation_mode"] = "dossier_snapshot_scenario"
        row["historical_eligibility"] = "not_verified_historical_replay"
        rows.append(row)
    return rows


def prior_forecast_comparison(row: Row) -> None:
    """Forecast-to-forecast YoY, distinct from actuals and historical vintages."""
    for key in (*PY_YOY, "fmi_increment_vs_py_forecast_pp"):
        row[key] = None
    prior = row.get("prior_year_forecast")
    status = row.get("prior_year_forecast_status") or "missing_prior_year_forecast"
    if prior is None:
        status = (
            status
            if status != "comparable_current_snapshot"
            else "missing_prior_year_forecast"
        )
    elif prior <= 0:
        status = "invalid_prior_year_forecast_nonpositive"
    elif status == "comparable_current_snapshot":
        required = (
            "baseline_subject",
            "baseline_scope",
            "baseline_currency",
            "baseline_unit_multiplier",
        )
        pairs = (
            ("baseline_subject", "prior_year_forecast_subject"),
            ("baseline_scope", "prior_year_forecast_scope"),
            ("baseline_currency", "prior_year_forecast_currency"),
            ("baseline_unit_multiplier", "prior_year_forecast_unit_multiplier"),
            ("forecast_target_start", "prior_year_forecast_target_start"),
            ("forecast_target_end", "prior_year_forecast_target_end"),
            ("baseline_revenue", "forecast_comparison_baseline_revenue"),
            (
                "forecast_comparison_native_quarter",
                "prior_year_forecast_native_quarter",
            ),
        )
        current_code = row.get("baseline_company_code") or row.get("company_code")
        if (
            not row.get("baseline_approved")
            or row.get("baseline_kind") != "unadjusted_forecast"
            or not all(row.get(k) for k in required)
        ):
            status = "current_baseline_unreviewed_or_incomplete"
        elif (
            not current_code
            or row.get("prior_year_forecast_company_code") != current_code
        ):
            status = "prior_forecast_company_mismatch"
        elif any(row.get(a) is None or row.get(a) != row.get(b) for a, b in pairs):
            status = "prior_forecast_comparability_changed_review_required"
        elif (
            not row.get("forecast_comparison_native_year")
            or row.get("prior_year_forecast_native_year")
            != row["forecast_comparison_native_year"] - 1
        ):
            status = "prior_forecast_fiscal_year_mismatch"
        elif (
            not row.get("prior_year_forecast_source")
            or not row.get("prior_year_forecast_reported_date")
            or not row.get("forecast_comparison_reported_date")
        ):
            status = "prior_forecast_missing_source_or_dates"
        else:
            start = date.fromisoformat(row["forecast_target_start"])
            end = date.fromisoformat(row["forecast_target_end"])
            current_end = date.fromisoformat(row["forecast_comparison_reported_date"])
            prior_end = date.fromisoformat(row["prior_year_forecast_reported_date"])
            try:
                in_windows = start <= current_end <= end and start.replace(
                    year=start.year - 1
                ) <= prior_end <= end.replace(year=end.year - 1)
            except ValueError:  # A leap-day target requires explicit alignment review.
                in_windows = False
            if not in_windows:
                status = "prior_forecast_outside_comparable_target_windows"
            else:
                status = "available_forecast_to_forecast_current_snapshot"
                for output, amount in PY_YOY.items():
                    value = row.get(amount)
                    if value is not None and value > 0:
                        row[output] = value / prior - 1
                if (
                    row["adjusted_forecast_vs_py_forecast_yoy"] is not None
                    and row["baseline_forecast_vs_py_forecast_yoy"] is not None
                ):
                    row["fmi_increment_vs_py_forecast_pp"] = 100 * (
                        row["adjusted_forecast_vs_py_forecast_yoy"]
                        - row["baseline_forecast_vs_py_forecast_yoy"]
                    )
    row["prior_year_forecast_comparison_status"] = status


def finalize(rows: list[Row], policy: Policy) -> tuple[list[Row], Row]:
    """Normalize selected scores; apply both scenarios to approved baselines."""
    rows = [dict(r) for r in rows]
    for row in rows:
        # CSV I/O decodes JSON-looking evidence. Keep this prose column textual.
        if isinstance(row.get("period_evidence"), (list, dict)):
            row["period_evidence"] = json.dumps(
                row["period_evidence"], ensure_ascii=False
            )
    scores = [
        r["raw_fmi"] for r in rows if r.get("include") and r.get("raw_fmi") is not None
    ]
    lo, hi = (min(scores), max(scores)) if scores else (None, None)
    cohort = {
        "members": [
            r["brand_id"]
            for r in rows
            if r.get("include") and r.get("raw_fmi") is not None
        ],
        "minimum": lo,
        "maximum": hi,
    }
    for row in rows:
        row.update(cohort_min=lo, cohort_max=hi, policy_version=policy.version)
        for key in (
            "display_fmi",
            "uplift_fraction",
            "legacy_uplift_fraction",
            "adjustment",
            "adjusted_forecast",
            "legacy_adjustment",
            "legacy_adjusted_forecast",
            "baseline_forecast_yoy",
            "adjusted_forecast_yoy",
            "legacy_adjusted_forecast_yoy",
            "source_legacy_uplift_fraction",
            "source_legacy_adjusted_forecast",
            "source_projection_difference",
        ):
            row[key] = None
        if row.get("include") and row.get("raw_fmi") is not None:
            assert lo is not None and hi is not None
            raw = row["raw_fmi"]
            display = half_up(
                policy.display_equal
                if lo == hi
                else policy.display_lower
                + (policy.display_upper - policy.display_lower) * (raw - lo) / (hi - lo)
            )
            row.update(
                display_fmi=display,
                uplift_fraction=uplift(display, policy),
                legacy_uplift_fraction=legacy_uplift(raw, policy),
            )
            if row.get("source_display_fmi") is not None:
                row["source_legacy_uplift_fraction"] = legacy_uplift(
                    row["source_display_fmi"], policy
                )
        baseline = row.get("baseline_revenue")
        if baseline is None:
            status = "missing_dossier_baseline"
        elif baseline <= 0:
            status = "invalid_baseline_nonpositive"
        elif row.get("baseline_kind") != "unadjusted_forecast":
            status = "baseline_already_adjusted_or_unknown"
        elif not row.get("baseline_approved"):
            status = "baseline_needs_review"
        elif not all(
            row.get(k)
            for k in (
                "baseline_source",
                "baseline_subject",
                "baseline_scope",
                "baseline_currency",
                "baseline_unit_multiplier",
                "forecast_target_label",
                "forecast_target_start",
                "forecast_target_end",
            )
        ):
            status = "baseline_missing_scope_unit_or_period"
        elif row["uplift_fraction"] is None:
            status = "missing_fmi"
        else:
            status = "available_dossier_scenario"
            for prefix, rate in (
                ("", row["uplift_fraction"]),
                ("legacy_", row["legacy_uplift_fraction"]),
            ):
                row[prefix + "adjustment"] = baseline * rate
                row[prefix + "adjusted_forecast"] = baseline * (1 + rate)
        row["forecast_status"] = status
        if (
            status == "available_dossier_scenario"
            and row["source_legacy_uplift_fraction"] is not None
        ):
            assert baseline is not None
            row["source_legacy_adjusted_forecast"] = baseline * (
                1 + row["source_legacy_uplift_fraction"]
            )
            if row.get("source_projected_forecast") is not None:
                row["source_projection_difference"] = (
                    row["source_legacy_adjusted_forecast"]
                    - row["source_projected_forecast"]
                )
        # Only explicitly matching prior-year observations support a YoY.
        prior = row.get("prior_year_actual")
        if (
            prior is not None
            and prior > 0
            and row.get("prior_year_actual_status") == "comparable"
        ):
            for output, amount in (
                ("baseline_forecast_yoy", baseline),
                ("adjusted_forecast_yoy", row["adjusted_forecast"]),
                ("legacy_adjusted_forecast_yoy", row["legacy_adjusted_forecast"]),
            ):
                row[output] = amount / prior - 1 if amount is not None else None
        row["missing_reasons"] = (
            "; ".join(
                s for s in (row["fmi_status"], status) if not s.startswith("available")
            )
            or None
        )
        prior_forecast_comparison(row)
    rank_categories(rows)
    return rows, cohort


def fields_for(rows: list[Row]) -> list[Field]:
    """One dictionary, used by the spreadsheet and app JSON."""
    keys = list(dict.fromkeys(HEADLINE + [k for row in rows for k in row]))
    fields = []
    for key in keys:
        group = (
            "Category rankings"
            if key.startswith("leaderboard_")
            else "Historical comparison"
            if key.startswith("weighted_reference_")
            else "App content"
            if key.startswith("app_")
            or key == "one_core_insight"
            or key.endswith(("_descriptor", "_insight", "_kpi", "_kpi_label"))
            else "Forecast"
            if any(
                s in key
                for s in (
                    "forecast",
                    "projection",
                    "baseline_revenue",
                    "baseline_currency",
                    "baseline_subject",
                    "baseline_scope",
                    "baseline_source",
                    "baseline_approved",
                    "baseline_kind",
                    "baseline_unit_multiplier",
                    "uplift",
                    "adjustment",
                    "prior_year_actual",
                    "source_sales",
                )
            )
            else "Social"
            if any(
                s in key
                for s in (
                    "social",
                    "median_metric",
                    "posts",
                    "current_start",
                    "current_end",
                    "baseline_start",
                    "baseline_end",
                )
            )
            else "Revenue and peers"
            if any(
                s in key
                for s in ("revenue", "growth", "gap_pp", "peer", "financial_period")
            )
            else "FMI"
            if any(
                s in key for s in ("fmi", "score", "contribution", "weight", "cohort")
            )
            else "Identity and evidence"
        )
        kind = (
            "array"
            if key == "peer_observations" or key in LOOKUP_ARRAYS
            else "boolean"
            if key in FLAGS
            else "datetime"
            if key
            in {"forecast_lookup_extracted_at", "prior_year_forecast_extracted_at"}
            else "date"
            if key in DATES
            or key in LOOKUP_DATES
            or key
            in {
                "weighted_reference_financial_period_start",
                "weighted_reference_financial_period_end",
                "weighted_reference_show_date",
            }
            else "number"
            if key in NUMBERS
            or key == "baseline_unit_multiplier"
            or key in {"ir_kpi", "social_kpi", "trend_kpi"}
            else "string"
        )
        unit = (
            "peer_records"
            if key == "peer_observations"
            else "source_records"
            if key in LOOKUP_ARRAYS
            else "fraction"
            if key in FRACTIONS or key in {"social_kpi", "trend_kpi"}
            else "pp"
            if key.endswith("_pp") or key == "ir_kpi"
            else "count"
            if key.endswith("posts")
            or key == "used_peer_count"
            or key
            in {
                "leaderboard_rank",
                "leaderboard_scored_count",
                "leaderboard_member_count",
            }
            else "currency_unit_multiplier"
            if key.endswith("unit_multiplier")
            else "fiscal_year_label"
            if key.endswith("native_year")
            else "score_points"
            if key == "reported_component_difference"
            or key.endswith("_contribution")
            or key.endswith("_score_difference")
            or key.endswith("_fmi_difference")
            else "score_0_100"
            if kind == "number"
            and ("fmi" in key or key.endswith("_score") or key.startswith("cohort_"))
            else "native_currency_units"
            if any(
                s in key
                for s in (
                    "revenue",
                    "forecast",
                    "projection",
                    "adjustment",
                    "source_sales",
                    "prior_year_actual",
                )
            )
            and kind == "number"
            else "calendar_date"
            if kind == "date"
            else "iso8601_utc"
            if kind == "datetime"
            else "number"
            if kind == "number"
            else "boolean"
            if kind == "boolean"
            else "text"
        )
        derivation = (
            "Dossier/source workbook transcription; source values remain unchanged"
        )
        if key == "company_code":
            derivation = (
                "Verified light.light_companies.company_code; company retrieval "
                "key, not ticker or shared symbol. See company_key_status, "
                "source and verification date."
            )
        if key in {
            "in_ranking_company_list",
            "tuesday_dinner_invited",
            "light_list_expected",
            "company_list_source",
            "company_list_comment",
            "app_category",
        }:
            derivation = (
                "Explicit supplied ranking/dinner company-list transcription; "
                "Y/N presence is expectation, not proof of a forecast. Native app "
                "category is separate from historical leaderboard categories."
            )
        elif key in {"light_list_check_status", "light_registry_presence"}:
            derivation = (
                "One-time authenticated registry match against supplied Y/N flag."
            )
        elif key == "baseline_is_parent_proxy":
            derivation = (
                "True means the forecast amount belongs to baseline_company_code's "
                "parent/group, not standalone brand revenue. Brand company_code "
                "never substitutes a parent key."
            )
        elif key == "forecast_native_company_code":
            derivation = (
                "Company key stored on the forecast source row. A verified registry "
                "ticker alias may differ from baseline_company_code and the app's "
                "company_code; those registry identity keys remain unchanged."
            )
        elif key in {
            "forecast_baseline_acceptance",
            "forecast_selection_method",
            "forecast_period_start_basis",
            "forecast_native_period_label",
            "forecast_native_reported_date",
            "forecast_monthly_fallback_status",
        }:
            derivation = (
                "Current client-demo forecast selection. Prefer Q4-ending native "
                "quarter, then nearby fiscal Q4, then three complete comparable "
                "months. Native labels/dates retained. Undocumented scale/scope "
                "acceptance is explicit, not audited or historical certification."
            )
        if key.startswith("leaderboard_"):
            derivation = (
                "Explicit input category copied once from supplied assignments; "
                "provisional competition rank 1 + count of higher rounded display FMI "
                "within current delivered category. Ties share rank, missing scores "
                "are unranked. Not historical ranks or a native app category mapping."
            )
        if key in PY_YOY or key == "fmi_increment_vs_py_forecast_pp":
            derivation = (
                "Matching current-snapshot PY forecast, same reviewed subject, "
                "currency, unit and native quarter, previous fiscal year: amount / "
                "prior_year_forecast - 1. FMI increment = 100 × (exponential YoY − "
                "baseline YoY) in pp. Not actuals YoY or an archived PY "
                "forecast vintage."
            )
        elif key.startswith("prior_year_forecast") or key.startswith(
            "forecast_comparison_"
        ):
            derivation = (
                "One-time read-only Light forecast query; current amount reconciled "
                "to approved dossier baseline; same company/native quarter and prior "
                "fiscal year. Native fiscal dates/labels retained. No historical "
                "forecast vintage is available; units match baseline display units."
            )
        if key.startswith("weighted_reference_"):
            derivation = (
                "Frozen historical weighted-delivery reference; never feeds "
                "current FMI or uplift. Difference = current minus reference. "
                "Historical content/revisions are reference-only."
            )
        elif key.endswith(
            ("_insight", "_descriptor", "_sentiment", "_kpi", "_kpi_label")
        ):
            derivation = (
                "Generated from final dossier metrics. IR KPI is peer gap in pp; "
                "Social KPI is source metric lift as fraction; Trend KPI is own "
                "growth as fraction, not numeric Strength. Missing KPI is null."
            )
        if key.startswith("forecast_lookup_") or key.startswith("forecast_candidate_"):
            derivation = (
                "Optional read-only Light query for missing forecast only; "
                "candidates do not feed FMI or uplift until baseline review "
                "is satisfied"
            )
        if key in {
            "raw_fmi",
            "weighted_component_fmi",
            "reported_component_difference",
        }:
            derivation = (
                "Selected reported headline, or explicit weighted_components mode. "
                "Weighted diagnostic = IR×50% + Social×30% + Trend×20%. "
                "Difference = diagnostic − reported headline."
            )
        elif key == "display_fmi":
            derivation = (
                "Selected cohort min–max to 70–98, half-up one decimal; "
                "equal cohort 84. Dynamic cohort."
            )
        elif key == "uplift_fraction":
            derivation = (
                "0.11 × expm1(8 × rounded display/100) / expm1(8). Business scenario."
            )
        elif key == "legacy_uplift_fraction":
            derivation = (
                "0 for selected raw score ≤60, else 0.03 + (raw−60)×0.002. "
                "Source workbook projections may use their own normalized score."
            )
        elif key == "source_legacy_uplift_fraction":
            derivation = (
                "Previous piecewise formula evaluated at original "
                "source_display_fmi, not current raw/display. "
                "Diagnostic reproduction of source workbook only."
            )
        elif key in {"source_legacy_adjusted_forecast", "source_projection_difference"}:
            derivation = (
                "Approved untreated baseline × (1 + source legacy rate); "
                "difference = reproduced minus source_projected_forecast. "
                "Source projection never feeds baseline."
            )
        elif key in {
            "adjustment",
            "adjusted_forecast",
            "legacy_adjustment",
            "legacy_adjusted_forecast",
        }:
            derivation = (
                "Approved unadjusted baseline × rate. "
                "Adjusted = baseline + adjustment. "
                "Native amount × baseline_unit_multiplier gives full currency units."
            )
        elif key == "historical_eligibility":
            derivation = (
                "Dossier snapshot only. Source capture/forecast vintages "
                "not established for strict historical replay."
            )
        elif key in {"earlier_growth", "latest_growth", "social_lift_fraction"}:
            derivation = (
                "Printed dossier value takes precedence. If missing and source "
                "observations are comparable, current/prior − 1; missing or "
                "nonpositive denominators remain unavailable."
            )
        fields.append(
            Field(
                key,
                LABELS.get(key, key.replace("_", " ").capitalize()),
                group,
                kind,
                unit,
                derivation=derivation,
                required=key == "company_code",
                influences_fmi=key
                in {
                    "reported_fmi",
                    "ir_score",
                    "social_score",
                    "trend_score",
                    "score_method",
                },
            )
        )
    return fields


def export_delivery(
    rows: list[Row],
    cohort: Row,
    policy: Policy,
    output: Path,
    *,
    previews: bool = False,
) -> Row:
    """Flat Excel rows and the same typed rows in a self-describing JSON contract."""
    reference_path = output / ".work" / "weighted-reference.json"
    reference = (
        json.loads(reference_path.read_text()) if reference_path.exists() else {}
    )
    delivered = enrich(
        [r for r in rows if r.get("include") and r.get("has_dossier_data")], reference
    )
    fields = fields_for(delivered or rows)
    keys = [f.key for f in fields]
    delivered = [{k: r.get(k) for k in keys} for r in delivered]
    delivered_by_id = {r["brand_id"]: r for r in delivered}
    calculation_traces = traces([delivered_by_id.get(r["brand_id"], r) for r in rows])
    contract = clean(
        {
            "schema_version": "fmi-dossier-delivery-v1",
            "source_mode": "dossier",
            "policy": policy.model_dump(),
            "cohort": cohort,
            "calculation_traces": calculation_traces,
            "leaderboards": leaderboards(delivered),
            "limitations": [
                "Dynamic cohort rescaling changes uplift even if a brand's "
                "dossier score is unchanged.",
                "70–98 produces positive new uplift for every scored brand.",
                "Business scenario, not calibrated predictive accuracy "
                "or strict historical replay.",
                "Dossier measurements are accepted for this client demo. New Light "
                "baselines use registry currency and accepted native full-unit scale; "
                "the forecast table does not publish units/reporting perimeter.",
                "Parent/group forecast scenarios are explicitly labelled and are "
                "not standalone brand revenue forecasts or fake brand company keys.",
                "Only missing forecast baselines may be queried from Light; "
                "database revenue/social measurements never replace dossier scores.",
                "PY forecast comparisons use a current Light snapshot, not archived "
                "forecasts as issued in the prior year, and are not actuals YoY.",
                "Category ranks cover this dossier delivery only. Source categories "
                "are not automatically mapped to the native app taxonomy; unknown "
                "assignments stay unranked.",
            ],
            "fields": [f.record() for f in fields],
            "rows": delivered,
        }
    )
    output.mkdir(parents=True, exist_ok=True)
    write_workbook(
        {
            "kind": "dossier-delivery",
            "policy": policy.model_dump(),
            "sheets": [
                {
                    "name": "Delivery",
                    "keys": keys,
                    "labels": [f.label for f in fields],
                    "rows": delivered,
                    "fields": [f.record() for f in fields],
                }
            ],
        },
        output / "dossier-calculated-delivery.xlsx",
        previews=previews,
    )
    (output / "dossier-calculated-delivery.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    save_handoff(delivered, reference, output)
    write_audit(calculation_traces, cohort, policy, output)
    return contract
