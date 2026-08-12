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

# Also install the optional Claude-API-backed classifier
pip install -e '.[classify]'

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
church-stats scan <url> --classify   # also classify outreach messaging (needs the classify extra)
church-stats scan-batch urls.txt     # scan many URLs concurrently; failures don't abort the batch
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
- **`src/church_stats/classifier/`** — optional (`[classify]` extra):
  `themes.py` (the controlled outreach-messaging taxonomy) and
  `messaging.py` (`classify_messaging`: Claude structured outputs, closed-set
  theme + confidence + evidence). Wired into `pipeline.scan_url` via
  `classify=True`, off by default. Kept as an optional dependency group so
  base scraping never requires an Anthropic API key. Credentials come from
  `ANTHROPIC_API_KEY` (shell env var or a gitignored project-root `.env`,
  loaded via `python-dotenv` — see `.env.example`); deliberately **not**
  from an `ant auth login` profile, since that credential type is meant for
  the Anthropic CLI/SDK generally, and mixing it with Claude Code's own
  credential resolution in the same shell risks Claude Code itself picking
  up an unintended auth source. A `.env` in the project root only affects
  `church-stats`'s own process — it's never read by Claude Code.
- **`src/church_stats/cli.py`** — Typer app wiring the scraper and
  repository together (`scan`, `scan-batch`, `list`, `show`). `scan-batch`
  runs URLs through a bounded `ThreadPoolExecutor` (`--concurrency`) and
  isolates per-URL failures (network errors, bad URLs, etc.) so one bad site
  doesn't abort the rest of the batch — each result is reported as it
  completes, with a summary at the end.

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
  This includes the `MessagingTheme` taxonomy in
  `classifier/themes.py` — it's a closed set (not freeform text) so it stays
  useful for aggregate analysis, and edits to it are schema changes too.

### Extraction philosophy

`extract.py` is best-effort and prefers structured sources: `schema.org`
JSON-LD (`@type: Church`/`LocalBusiness`/etc.) is trusted over meta tags,
which are trusted over regex sniffing of page text. A field extraction
should leave the field `None` rather than guess when it isn't confident.

## Issue tracking

Feature requests, bugs, and schema-change proposals are tracked as **GitHub
Issues** on this repo (`gh issue list` / `gh issue create`), not as local
TODO files or comments in code.

## Git workflow

`main` is branch-protected: direct pushes are rejected for everyone,
including admins (`enforce_admins: true`). All changes go through a branch +
pull request:

```bash
git checkout -b <type>/<short-description> main   # e.g. feat/batch-scan, fix/slugify-unicode
# ... make changes, commit ...
git push -u origin <branch>
gh pr create --fill
gh pr merge --squash --delete-branch
```

No approving review is required (`required_approving_review_count: 0`) since
this is a solo-maintainer repo and GitHub doesn't allow self-approval — the
PR itself, not a review, is the gate. A plain `gh pr merge` is sufficient;
`--admin` isn't needed since nothing is left to bypass.
