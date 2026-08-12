"""Command-line interface for church-stats."""

from __future__ import annotations

import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Annotated

import typer

from church_stats.models import ChurchRecord
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
    classify: Annotated[
        bool,
        typer.Option(
            help="Classify the church's outreach messaging via the Claude API "
            r"(requires \[classify] extra and Anthropic credentials)."
        ),
    ] = False,
    classifier_model: Annotated[
        str | None,
        typer.Option(help="Model to use for --classify. Defaults to a low-cost model."),
    ] = None,
) -> None:
    """Scan a church's website and print (and optionally save) the resulting record.

    The record id is derived from the site's domain, so re-scanning the same
    site overwrites its existing record rather than creating a duplicate.
    """
    repo = _repository()
    try:
        record = scan_url(url, classify=classify, classifier_model=classifier_model)
    except ImportError:
        typer.echo(
            "--classify requires the 'classify' extra: pip install -e '.[classify]'", err=True
        )
        raise typer.Exit(code=1) from None
    except Exception as exc:
        if not classify:
            raise
        typer.echo(f"Scan failed: {exc}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(record.model_dump_json(indent=2))

    if save:
        path = repo.save(record)
        typer.echo(f"Saved to {path}", err=True)


def _read_urls(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def _scan_one(
    url: str, *, classify: bool, classifier_model: str | None
) -> tuple[str, ChurchRecord | None, str | None]:
    try:
        record = scan_url(url, classify=classify, classifier_model=classifier_model)
    except Exception as exc:
        return url, None, str(exc)
    return url, record, None


@app.command(name="scan-batch")
def scan_batch(
    urls_file: Annotated[
        Path, typer.Argument(help="Path to a file with one church URL per line (# comments ok).")
    ],
    save: Annotated[
        bool, typer.Option(help="Save each resulting record to the data store.")
    ] = True,
    classify: Annotated[
        bool,
        typer.Option(
            help="Classify each church's outreach messaging via the Claude API "
            r"(requires \[classify] extra and Anthropic credentials)."
        ),
    ] = False,
    classifier_model: Annotated[
        str | None,
        typer.Option(help="Model to use for --classify. Defaults to a low-cost model."),
    ] = None,
    concurrency: Annotated[int, typer.Option(help="Max number of churches to scan at once.")] = 5,
    delay: Annotated[
        float,
        typer.Option(help="Seconds to wait between dispatching each scan (politeness throttle)."),
    ] = 0.0,
) -> None:
    """Scan many church websites from a file, one URL per line.

    Failures (network errors, bad URLs, etc.) are reported per-URL and don't
    abort the rest of the batch. Each record's id is derived from its site's
    domain, so re-scanning a URL already in the store overwrites that record.
    """
    if concurrency < 1:
        typer.echo("--concurrency must be at least 1", err=True)
        raise typer.Exit(code=1)

    urls = _read_urls(urls_file)
    if not urls:
        typer.echo(f"No URLs found in {urls_file}", err=True)
        raise typer.Exit(code=1)

    if classify:
        try:
            import church_stats.classifier.messaging  # noqa: F401
        except ImportError:
            typer.echo(
                "--classify requires the 'classify' extra: pip install -e '.[classify]'",
                err=True,
            )
            raise typer.Exit(code=1) from None

    repo = _repository()
    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures: list[Future[tuple[str, ChurchRecord | None, str | None]]] = []
        for url in urls:
            futures.append(
                executor.submit(
                    _scan_one, url, classify=classify, classifier_model=classifier_model
                )
            )
            if delay:
                time.sleep(delay)

        for future in as_completed(futures):
            url, record, error = future.result()
            if record is None:
                typer.echo(f"FAILED  {url}: {error}", err=True)
                failed.append((url, error or "unknown error"))
                continue
            if save:
                repo.save(record)
            typer.echo(f"OK      {url} -> {record.id}")
            succeeded.append(url)

    typer.echo("")
    typer.echo(f"Scanned {len(urls)}: {len(succeeded)} succeeded, {len(failed)} failed.")
    if failed:
        typer.echo("Failures:", err=True)
        for url, reason in failed:
            typer.echo(f"  {url}: {reason}", err=True)
        raise typer.Exit(code=1)


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
