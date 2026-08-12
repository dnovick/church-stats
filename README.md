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

# Uses ANTHROPIC_API_KEY (or an `ant auth login` profile) for credentials
church-stats scan https://example-church.org --classify
```

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
