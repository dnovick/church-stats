# church-stats

A data collection and analysis toolset for harvesting, managing, and analyzing
information about Christian churches.

Given a church's website URL, `church-stats` scans the site and extracts
structured information (name, denomination, address, contact info, service
times, leaders, social links, ...) into a local JSON store — one file per
church under `data/churches/`. The schema is intentionally flexible and
evolves over time; see `CLAUDE.md` for the schema-evolution convention.
Re-scanning a URL already in the store merges the fresh scrape into the
existing record instead of overwriting it, so manually-added fields (notes,
tags) survive re-scans — see "Duplicates and merging" below.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## Usage

```bash
# Scan a church's website and save the resulting record
church-stats scan https://example-church.org

# Scan without saving
church-stats scan https://example-church.org --no-save

# List stored churches
church-stats list

# Show one stored record
church-stats show example-church-org

# Scan many churches from a file (one URL per line, # comments ok)
church-stats scan-batch urls.txt
```

`scan-batch` scans URLs concurrently (`--concurrency`, default 5) and
reports failures per-URL instead of aborting the whole run — see the
`Scanned N: X succeeded, Y failed` summary at the end. Use `--delay` to
space out requests if you want to be gentler on the sites you're scanning.

### Service times

`service_times` is populated from `schema.org` JSON-LD when a site
publishes it (most reliable), or otherwise parsed from free text near a
heading like "Service Times" or "When We Meet" — handling things like
"Sundays 9am & 11am" or "Sun 9:00 / 11:00 AM" (a shared am/pm marker
applies to the whole list) and an optional `(Language)` hint. A day found
with no confidently-parseable time is only kept when the same block
resolved a real time elsewhere, and its original text is preserved in
`raw_text` for review. This is homepage-only — a church whose times live on
a separate "Visit" page won't be picked up yet.

### Denomination, leaders, and alternate names

`denomination` is matched against a curated list of known U.S. denomination
names/abbreviations (e.g. "Southern Baptist", "PCUSA") found anywhere on
the page — no guessing from generic words. `leaders` comes from JSON-LD
`founder`/`employee` entries when present, or free text near a "Meet the
Team"/"Our Staff" heading ("Name, Title" or "Title: Name"). `also_known_as`
only comes from JSON-LD `alternateName` — there's no reliable free-text
fallback for it. `tags` stays manual-only (alongside `notes`); there's no
reliable page signal for a subjective label like "large" or "contemporary".

If the homepage doesn't have `leaders`/`also_known_as`, `scan` follows a
same-domain "Staff"/"Leadership"/"About" nav link (at most one of each) and
checks that page too, so these aren't purely homepage-only like service
times and denomination are. Pass `--no-crawl` for a faster, homepage-only
scan if you don't need the extra reach.

### Duplicates and merging

The same church can end up stored under two different ids if it's reachable
at more than one domain/URL. `church-stats duplicates` flags likely-duplicate
pairs (by similar name, matching phone number, or same city/region + a
weaker name match) for you to review — it never merges anything on its own:

```bash
church-stats duplicates

church-stats merge <keep-id> <drop-id>   # combine and delete drop-id's record
```

Fields already set on `<keep-id>` win; `<drop-id>` only fills in fields
`<keep-id>` is missing. Pass `--yes` to skip the confirmation prompt.

### Classifying outreach messaging (optional)

`church-stats scan --classify` uses the Claude API to classify a church's
homepage into a controlled taxonomy of outreach-messaging themes (e.g.
community-focused vs. spiritual-experience-focused) — see
`src/church_stats/classifier/themes.py` for the full list. This is opt-in
since it's an extra paid API call per scan:

```bash
pip install -e '.[classify]'
cp .env.example .env   # then edit .env and set ANTHROPIC_API_KEY

church-stats scan https://example-church.org --classify
```

Credentials come from `ANTHROPIC_API_KEY` — either already set in your shell,
or in a gitignored `.env` file in the project root (see `.env.example`). The
`.env` file is only read by `church-stats` itself and never touches your
shell environment, so it's safe to use even if you also use Claude Code
(which reads its own subscription credentials separately) in this directory.

## Development

```bash
python -m mypy src
python -m flake8
python -m black --check .
python -m isort --check .
pytest
```

Feature requests, bugs, and schema-change proposals are tracked as GitHub
Issues on this repo, not in local TODO files.
