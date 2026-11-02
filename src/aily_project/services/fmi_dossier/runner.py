"""Independent dossier task registered in the project's single Click CLI."""

import json
from datetime import date
from pathlib import Path

import click
import yaml
from dotenv import load_dotenv

from .categories import apply_categories, read_categories
from .excel import export_delivery, finalize, read_excel, score_rows
from .model import clean
from .policy import Policy


@click.command("fmi-dossier")
@click.option(
    "--inputs",
    "inputs_path",
    type=click.Path(exists=True, path_type=Path),
    default="scripts/fmi-dossier/inputs/FMI_dossier_inputs.xlsx",
    show_default=True,
)
@click.option(
    "--categories",
    "categories_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default="scripts/fmi-dossier/inputs/FMI index companies_tuesdaydinner.xlsx",
    show_default=True,
    help="Authoritative company/category assignments in columns A/B; no guessing.",
)
@click.option(
    "--policy",
    "policy_path",
    type=click.Path(exists=True, path_type=Path),
    default="scripts/fmi-dossier/policy.yaml",
    show_default=True,
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default="outputs/fmi-dossier",
    show_default=True,
)
@click.option(
    "--query-missing-forecasts",
    is_flag=True,
    help="Read Light only for missing or unreviewed dossier baseline amounts; "
    "never refresh score measurements.",
)
@click.option("--forecast-start", default="2026-10-01", show_default=True)
@click.option("--forecast-end", default="2026-12-31", show_default=True)
@click.option("--previews", is_flag=True)
def fmi_dossier(
    inputs_path: Path,
    categories_path: Path,
    policy_path: Path,
    output: Path,
    query_missing_forecasts: bool,
    forecast_start: str,
    forecast_end: str,
    previews: bool,
) -> None:
    """Dossier Excel → metrics, normalized FMI, both uplifts and Excel/JSON."""
    load_dotenv(override=False)
    rows = apply_categories(read_excel(inputs_path), read_categories(categories_path))
    policy = Policy.model_validate(yaml.safe_load(policy_path.read_text()))
    if query_missing_forecasts and any(
        r.get("include")
        and (r.get("baseline_revenue") is None or not r.get("baseline_approved"))
        for r in rows
    ):
        from aily_py_commons.aily_settings import AilySettings

        from .connections import light_connection
        from .forecast import query_missing

        AilySettings()
        with light_connection() as client:
            rows, audit = query_missing(
                rows,
                client,
                date.fromisoformat(forecast_start),
                date.fromisoformat(forecast_end),
            )
        work = output / ".work"
        work.mkdir(parents=True, exist_ok=True)
        (work / "forecast-lookup.json").write_text(
            json.dumps(clean(audit), ensure_ascii=False, indent=2, allow_nan=False)
            + "\n"
        )
    rows, cohort = finalize(score_rows(rows, policy), policy)
    contract = export_delivery(rows, cohort, policy, output, previews=previews)
    click.echo(
        f"{len(contract['rows'])} rows; {len(cohort['members'])} FMI scores; "
        + f"{sum(r['adjusted_forecast'] is not None for r in contract['rows'])} "
        "adjusted forecasts"
    )
