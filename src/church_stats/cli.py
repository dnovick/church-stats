"""Command-line interface for church-stats."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from church_stats.scraper.pipeline import scan_url
from church_stats.storage import ChurchNotFoundError, ChurchRepository

app = typer.Typer(help="Harvest and manage structured data about churches.")

DEFAULT_DATA_DIR = Path("data/churches")


def _repository() -> ChurchRepository:
    return ChurchRepository(DEFAULT_DATA_DIR)


@app.command()
def scan(
    url: Annotated[str, typer.Argument(help="URL of the church's website to scan.")],
    save: Annotated[bool, typer.Option(help="Save the resulting record to the data store.")] = True,
) -> None:
    """Scan a church's website and print (and optionally save) the resulting record.

    The record id is derived from the site's domain, so re-scanning the same
    site overwrites its existing record rather than creating a duplicate.
    """
    repo = _repository()
    record = scan_url(url)
    typer.echo(record.model_dump_json(indent=2))

    if save:
        path = repo.save(record)
        typer.echo(f"Saved to {path}", err=True)


@app.command(name="list")
def list_churches() -> None:
    """List the ids of all stored churches."""
    repo = _repository()
    for church_id in repo.list_ids():
        typer.echo(church_id)


@app.command()
def show(church_id: Annotated[str, typer.Argument(help="Id of a stored church record.")]) -> None:
    """Print one stored church record as JSON."""
    repo = _repository()
    try:
        record = repo.load(church_id)
    except ChurchNotFoundError:
        typer.echo(f"No church found with id {church_id!r}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(record.model_dump_json(indent=2))


if __name__ == "__main__":
    app()
