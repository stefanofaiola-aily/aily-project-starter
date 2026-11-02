"""Single entry point for project services."""

import click

from aily_project.services.database.runner import database
from aily_project.services.fmi.runner import fmi
from aily_project.services.fmi_dossier.html_delivery import fmi_dossier_html
from aily_project.services.fmi_dossier.runner import fmi_dossier


@click.group()
def cli() -> None:
    """Run standalone Aily project tasks."""


cli.add_command(database)
cli.add_command(fmi)
cli.add_command(fmi_dossier)
cli.add_command(fmi_dossier_html)


if __name__ == "__main__":
    cli()
