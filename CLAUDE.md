# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`church-stats` is a Python toolset for harvesting, managing, and analyzing
structured information about Christian churches. The initial capability is
scanning a church's website (given a URL) and extracting data — name,
address, contact info, service times, social links, etc. — into a local JSON
store.

## Commands

```bash
# Install (editable, with dev dependencies)
pip install -e '.[dev]'

# Type check (strict) — must be clean before committing
python -m mypy src

# Lint — must be clean before committing
python -m flake8

# Format
python -m black .
python -m isort .

# Run tests
pytest
pytest tests/test_storage.py::test_save_and_load_round_trip  # single test

# CLI
church-stats scan <url>          # scan a church site and save the record
church-stats scan <url> --no-save
church-stats list
church-stats show <church-id>
```

All tool configuration (mypy, flake8, black, isort, pytest, build backend)
lives in `pyproject.toml` — do not add separate `.flake8`, `setup.cfg`, or
`pytest.ini` files. flake8 itself doesn't read `pyproject.toml` natively;
the `Flake8-pyproject` dev dependency is what makes `[tool.flake8]` work.

mypy runs in `strict` mode — new code must be fully typed. Always run mypy
and flake8 after changes and fix everything they flag; don't suppress
warnings with unjustified `# type: ignore` / `# noqa` comments.

## Architecture

- **`src/church_stats/models.py`** — the `ChurchRecord` Pydantic schema
  (plus `Address`, `ServiceTime`, `Leader`, `SocialLinks`, `SourceRecord`).
  This is the single source of truth for what a church record looks like.
- **`src/church_stats/storage.py`** — `ChurchRepository`: one JSON file per
  church under `data/churches/<id>.json`, id derived from the site's domain
  via `slugify`. Records are committed to git as they accumulate.
- **`src/church_stats/scraper/`** — `fetch.py` (HTTP via `requests`),
  `extract.py` (heuristic `BeautifulSoup`/JSON-LD extraction into an
  `ExtractedData` dataclass), `pipeline.py` (`scan_url`: fetch → extract →
  build a `ChurchRecord`, without saving it).
- **`src/church_stats/cli.py`** — Typer app wiring the scraper and
  repository together (`scan`, `list`, `show`).

### Schema evolution

The schema needs to grow over time without breaking existing data. The
mechanism:

- `ChurchRecord` uses `model_config = ConfigDict(extra="allow")`, so
  unmodeled fields can be stashed on a record (e.g. by the scraper or a
  manual edit) without failing validation.
- Fields that turn out to be commonly useful get **promoted** into the model
  explicitly, in a normal code change — don't leave load-bearing data
  permanently unmodeled in `extra`.
- `schema_version` on `ChurchRecord` exists for the rare case a change is
  actually breaking (renaming/removing a field, changing its type) and
  `storage.py` needs a migration path. Purely additive fields don't need a
  version bump.
- Propose schema changes as a GitHub issue using the "Schema change" issue
  template before making them, since the schema is shared, persisted data.

### Extraction philosophy

`extract.py` is best-effort and prefers structured sources: `schema.org`
JSON-LD (`@type: Church`/`LocalBusiness`/etc.) is trusted over meta tags,
which are trusted over regex sniffing of page text. A field extraction
should leave the field `None` rather than guess when it isn't confident.

## Issue tracking

Feature requests, bugs, and schema-change proposals are tracked as **GitHub
Issues** on this repo (`gh issue list` / `gh issue create`), not as local
TODO files or comments in code.
