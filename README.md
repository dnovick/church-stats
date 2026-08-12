# church-stats

A data collection and analysis toolset for harvesting, managing, and analyzing
information about Christian churches.

Given a church's website URL, `church-stats` scans the site and extracts
structured information (name, address, contact info, service times, social
links, ...) into a local JSON store — one file per church under
`data/churches/`. The schema is intentionally flexible and evolves over time;
see `CLAUDE.md` for the schema-evolution convention.

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
```

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
