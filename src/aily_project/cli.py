"""Single entry point for project services."""

import click

from aily_project.services.database.runner import database
from aily_project.services.fmi.runner import fmi


@click.group()
def cli() -> None:
    """Run standalone Aily project tasks."""


cli.add_command(database)
cli.add_command(fmi)


if __name__ == "__main__":
    cli()
