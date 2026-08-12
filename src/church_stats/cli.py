"""Command-line interface for church-stats."""

from __future__ import annotations

import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Annotated

import typer

from church_stats.dedupe import find_duplicates
from church_stats.models import ChurchRecord
from church_stats.scraper.pipeline import scan_url
from church_stats.storage import ChurchNotFoundError, ChurchRepository

app = typer.Typer(help="Harvest and manage structured data about churches.")

DEFAULT_DATA_DIR = Path("data/churches")


def _repository() -> ChurchRepository:
    return ChurchRepository(DEFAULT_DATA_DIR)


def _merge_if_exists(repo: ChurchRepository, record: ChurchRecord) -> ChurchRecord:
    """Merge into any existing record with the same id, so a re-scan can't
    silently overwrite manually-added fields or fields the new scrape
    happened to miss."""
    if repo.exists(record.id):
        return repo.merge(repo.load(record.id), record)
    return record


def _load_or_exit(repo: ChurchRepository, church_id: str) -> ChurchRecord:
    try:
        return repo.load(church_id)
    except ChurchNotFoundError:
        typer.echo(f"No church found with id {church_id!r}", err=True)
        raise typer.Exit(code=1) from None


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
    site merges into its existing record (see `church-stats merge` for
    combining records for the same church found at different URLs) rather
    than overwriting it wholesale -- manually-added fields and anything the
    new scrape didn't find are preserved.
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

    if save:
        record = _merge_if_exists(repo, record)
        path = repo.save(record)
        typer.echo(record.model_dump_json(indent=2))
        typer.echo(f"Saved to {path}", err=True)
    else:
        typer.echo(record.model_dump_json(indent=2))


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
    domain, so re-scanning a URL already in the store merges into the
    existing record rather than overwriting it wholesale.
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
                record = _merge_if_exists(repo, record)
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
    record = _load_or_exit(repo, church_id)
    typer.echo(record.model_dump_json(indent=2))


@app.command()
def duplicates() -> None:
    """Scan all stored churches for likely duplicates (by name/phone/address).

    This only flags candidate pairs for review -- it never merges anything
    on its own. Use `church-stats merge <keep-id> <drop-id>` on a pair once
    you've confirmed they're the same church.
    """
    repo = _repository()
    candidates = find_duplicates(list(repo.all()))

    if not candidates:
        typer.echo("No likely duplicates found.")
        return

    for candidate in candidates:
        typer.echo(f"{candidate.first_id}  <->  {candidate.second_id}")
        for reason in candidate.reasons:
            typer.echo(f"  - {reason}")

    typer.echo("")
    typer.echo(
        f"{len(candidates)} likely duplicate pair(s). Review and run "
        "`church-stats merge <keep-id> <drop-id>` to combine a pair."
    )


@app.command(name="merge")
def merge_command(
    keep_id: Annotated[
        str, typer.Argument(help="Id of the record to keep -- it wins on conflicting fields.")
    ],
    drop_id: Annotated[
        str, typer.Argument(help="Id of the duplicate record to merge in, then delete.")
    ],
    yes: Annotated[bool, typer.Option("--yes", help="Skip the confirmation prompt.")] = False,
) -> None:
    """Merge two records that represent the same church, keeping `keep_id`.

    Fields already set on `keep_id` win; `drop_id` only fills in fields
    `keep_id` is missing. `drop_id`'s record is deleted once merged.
    """
    repo = _repository()
    keep_record = _load_or_exit(repo, keep_id)
    drop_record = _load_or_exit(repo, drop_id)

    if not yes:
        typer.confirm(
            f"Merge {drop_id!r} ({drop_record.name!r}) into {keep_id!r} ({keep_record.name!r})? "
            f"This deletes {drop_id!r}'s record.",
            abort=True,
        )

    merged = repo.merge(existing=drop_record, incoming=keep_record)
    merged = merged.model_copy(
        update={
            "id": keep_record.id,
            "created_at": min(keep_record.created_at, drop_record.created_at),
        }
    )
    repo.save(merged)
    repo.delete(drop_id)
    typer.echo(f"Merged {drop_id!r} into {keep_id!r}.")


if __name__ == "__main__":
    app()
