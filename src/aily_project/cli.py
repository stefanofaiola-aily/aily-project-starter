"""Single entry point for project services."""

import click

from aily_project.services.database.runner import database


@click.group()
def cli() -> None:
    """Run standalone Aily project tasks."""


cli.add_command(database)


if __name__ == "__main__":
    cli()
