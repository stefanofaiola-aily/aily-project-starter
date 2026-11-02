"""Small presentation export of completed dossier results; never rescore or query."""

import json
import math
from pathlib import Path
from typing import TypeGuard

import click

from .excel import WEIGHTED_COLUMNS
from .model import Field, Row, clean
from .workbook import write_workbook

# Keep v6's legacy header contract. Presentation history uses historical sales
# YoY for 2024/25 and adjusted/PY forecast for 2026; full source rows stay intact.
PRESENTATION_COLUMNS = WEIGHTED_COLUMNS[:35]
DETAIL_COLUMNS = [
    ("projection_label", "Projection label"),
    ("forecast_target_label", "Forecast target"),
    ("baseline_revenue", "Forecast baseline before FMI"),
    ("uplift_fraction", "Exponential uplift (%)"),
    ("adjusted_forecast", "Adjusted forecast after FMI"),
    ("prior_year_forecast", "PY forecast"),
    ("baseline_forecast_vs_py_forecast_yoy", "Baseline forecast vs PY (%)"),
    ("baseline_currency", "Forecast currency"),
    ("baseline_unit_multiplier", "Amount unit multiplier"),
    ("historical_comparison_basis", "Historical comparison basis"),
    ("revenue_methodology", "Revenue methodology"),
    ("fmi_status", "FMI status"),
    ("forecast_status", "Forecast status"),
    ("brand_id", "Brand ID"),
    ("presentation_source", "Source reference"),
]
COLUMNS = PRESENTATION_COLUMNS + DETAIL_COLUMNS
PROJECTION_LABEL = "Adjusted forecast vs PY forecast"
HISTORY_BASIS = (
    "2024/25: source Q4 sales YoY. 2026: adjusted forecast vs PY forecast, "
    "not actual sales. Source fiscal/calendar periods and social windows "
    "vary by brand."
)


def _number(value: object) -> TypeGuard[int | float]:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _percent(value: object) -> str:
    return f"{float(value):+.2%}" if _number(value) else "unavailable"


def _amount(row: Row, key: str) -> str:
    value = row.get(key)
    if not _number(value):
        return "unavailable"
    currency = row.get("baseline_currency") or "currency unspecified"
    multiplier = row.get("baseline_unit_multiplier")
    unit = {1: "", 1000: " thousand", 1000000: " million"}.get(multiplier)
    if unit is None:
        unit = f" (unit multiplier {multiplier or 'unspecified'})"
    return f"{currency} {value:,.3f}{unit}"


def _projection_copy(row: Row) -> tuple[str, str]:
    """Short business description, separate from audit/calculation detail."""
    yoy = row.get("adjusted_forecast_vs_py_forecast_yoy")
    social = [
        f"{_percent(row[key])} ({year})"
        for year in (2024, 2025, 2026)
        if _number(row.get(key := f"source_social_{year}"))
    ]
    parts = ["Source social lift: " + ", ".join(social) + "."] if social else []
    for year in (2025, 2024):
        growth = row.get(f"source_q4_sales_yoy_{year}")
        if _number(growth):
            parts.append(f"Q4 sales YoY was {_percent(growth)} in {year}.")
            break
    if _number(yoy):
        uplift = row.get("uplift_fraction")
        parts.append(
            (f"With {_percent(uplift)} FMI uplift, " if _number(uplift) else "")
            + f"the adjusted 2026 forecast is {_percent(yoy)} vs PY forecast."
        )
    else:
        parts.append("The adjusted 2026 forecast comparison is unavailable.")
    if row.get("baseline_is_parent_proxy"):
        parts.append("Forecast uses a parent/group proxy.")
    statistics = (
        f"{row.get('forecast_target_label') or 'Selected forecast period'}: "
        f"baseline {_amount(row, 'baseline_revenue')}; "
        f"FMI uplift {_percent(row.get('uplift_fraction'))}; "
        f"adjusted forecast {_amount(row, 'adjusted_forecast')}; "
        f"PY forecast {_amount(row, 'prior_year_forecast')}. "
        "Projection headline = adjusted forecast / matching PY forecast - 1. "
        "The exponential uplift is applied to the untreated baseline. "
        "PY is a current forecast snapshot for the prior target period, not actual "
        "sales or a verified historical forecast vintage."
    )
    return " ".join(parts), statistics


def _methodology(row: Row) -> str:
    parts = [
        f"Dossier financial score subject: "
        f"{row.get('financial_subject') or 'unspecified'}; "
        f"period: {row.get('financial_period_label') or 'unspecified'}.",
        f"Social comparison: {row.get('current_window') or 'unspecified'} versus "
        f"{row.get('baseline_window') or 'unspecified'}; "
        f"metric: {row.get('social_metric') or 'unspecified'}.",
        f"Forecast subject: {row.get('baseline_subject') or 'unspecified'}; "
        f"scope: {row.get('baseline_scope') or 'unspecified'}.",
        "Exponential uplift uses normalized FMI and is a business scenario, "
        "not calibrated predictive accuracy. Current Light snapshots are not "
        "strict replay or actual sales.",
    ]
    if row.get("score_source") == "published_delivery":
        parts[:2] = [
            "Scores, normalized FMI and card KPIs/periods are preserved from "
            + str(row.get("published_source_reference"))
            + ".",
            "The card insights describe the published measurement periods. "
            "Other dossier measurements remain alternative audit context, not "
            "inputs used to recompute these published scores.",
        ]
    if row.get("source_snapshot_reference"):
        parts.insert(
            2,
            "Historical sales/social data are separate from locked score cards: "
            + str(row["source_snapshot_reference"])
            + ". Missing source years remain unavailable; "
            "supplied zeroes are retained.",
        )
    if row.get("baseline_is_parent_proxy"):
        parts.append("Forecast is a parent/group proxy, not standalone brand revenue.")
    elif row.get("financial_subject") and row.get("financial_subject") != row.get(
        "baseline_subject"
    ):
        parts.append(
            "The dossier financial subject differs from the forecast subject; "
            "this is a hybrid/proxy scenario, not standalone financial comparability."
        )
    return "\n".join(parts)


def build_payload(contract: Row) -> Row:
    """Select final values; no cohort changes, uplift mathematics or imputation."""
    if contract.get("schema_version") != "fmi-dossier-delivery-v2":
        raise ValueError("Expected a completed fmi-dossier-delivery-v2 JSON export")
    fields = {f["field_key"]: f for f in contract["fields"]}
    selected_fields = []
    for key, label in COLUMNS:
        field = dict(fields.get(key) or Field(key, label, "HTML presentation").record())
        field["excel_label"] = label
        # The legacy header is retained solely for the current v6 importer.
        if key in {"source_q4_vs_baseline_2024", "source_q4_vs_baseline_2025"}:
            year = key[-4:]
            source_key = f"source_q4_sales_yoy_{year}"
            field.update(
                source_fields=[source_key],
                source_kind="presentation_mapping",
                source_reference="Completed dossier delivery; supplied historical "
                "sales YoY v2 snapshot, not same-year baseline variance",
                derivation=f"Source Q4 {year} sales / preceding-year Q4 sales - 1; "
                "selects the supplied ratio without recalculating source amounts. "
                "No fallback to same-year baseline variance.",
                description=f"Q4 {year} sales YoY; legacy import header retained",
                unit="fraction",
                type="number",
            )
        elif key == "source_q4_vs_baseline_2026":
            field.update(
                source_fields=["adjusted_forecast_vs_py_forecast_yoy"],
                source_kind="presentation_mapping",
                source_reference="Completed dossier delivery; "
                "new adjusted/PY forecast ratio",
                derivation="adjusted_forecast / matching prior_year_forecast - 1; "
                "already calculated in the full delivery, not a legacy uplift rate",
                description=PROJECTION_LABEL + "; not frozen legacy uplift",
                unit="fraction",
                type="number",
            )
        elif key in {"source_insights_descriptive", "source_insights_statistics"}:
            field.update(
                source_kind="presentation_mapping",
                source_reference="Completed dossier delivery; forecast copy generated "
                "from final values, not frozen original text",
                source_fields=[
                    "source_social_2024",
                    "source_social_2025",
                    "source_social_2026",
                    "source_q4_sales_yoy_2024",
                    "source_q4_sales_yoy_2025",
                    "forecast_target_label",
                    "baseline_revenue",
                    "uplift_fraction",
                    "adjusted_forecast",
                    "prior_year_forecast",
                    "adjusted_forecast_vs_py_forecast_yoy",
                ],
                derivation="Descriptive: concise business summary from final "
                "social, historical sales YoY and adjusted/PY forecast values. "
                "Statistics: detailed calculation explanation retained in "
                "Excel/JSON, not displayed as the HTML description.",
            )
        selected_fields.append(field)
    rows = []
    for source in contract["rows"]:
        row = {key: source.get(key) for key, _ in COLUMNS}
        for year in (2024, 2025):
            value = source.get(f"source_q4_sales_yoy_{year}")
            row[f"source_q4_vs_baseline_{year}"] = value if _number(value) else None
        value = source.get("adjusted_forecast_vs_py_forecast_yoy")
        row["source_q4_vs_baseline_2026"] = value if _number(value) else None
        row["source_insights_descriptive"], row["source_insights_statistics"] = (
            _projection_copy(source)
        )
        row["projection_label"] = PROJECTION_LABEL
        row["historical_comparison_basis"] = HISTORY_BASIS
        row["revenue_methodology"] = _methodology(source)
        row["presentation_source"] = "; ".join(
            str(source[key])
            for key in (
                "source_document",
                "baseline_source",
                "prior_year_forecast_source",
                "source_snapshot_reference",
            )
            if source.get(key)
        )
        rows.append(row)
    return {
        "sheets": [
            {
                "name": "Delivery",
                "keys": [key for key, _ in COLUMNS],
                "labels": [label for _, label in COLUMNS],
                "fields": selected_fields,
                "rows": rows,
            }
        ]
    }


@click.command("fmi-dossier-html")
@click.option(
    "--source",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default="outputs/fmi-dossier/dossier-calculated-delivery.json",
    show_default=True,
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default="outputs/fmi-dossier-html/html-delivery.xlsx",
    show_default=True,
)
@click.option("--previews", is_flag=True)
def fmi_dossier_html(source: Path, output: Path, previews: bool) -> None:
    """Export completed dossier results for HTML; no AWS or score recalculation."""
    payload = build_payload(json.loads(source.read_text()))
    write_workbook(payload, output, previews=previews, template="html_workbook.mjs")
    spec = payload["sheets"][0]
    rows = spec["rows"]
    output.with_suffix(".json").write_text(
        json.dumps(
            clean(
                {
                    "schema_version": "fmi-dossier-html-v1",
                    "source": str(source),
                    "fields": spec["fields"],
                    "rows": rows,
                }
            ),
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )
    click.echo(
        f"{len(rows)} brands; {len(COLUMNS)} columns; "
        f"{sum(r['source_q4_vs_baseline_2026'] is not None for r in rows)} "
        f"new PY-forecast comparisons. Saved {output} and {output.with_suffix('.json')}"
    )
