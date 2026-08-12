from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pytest
from typer.testing import CliRunner

from church_stats import cli
from church_stats.models import ChurchRecord
from church_stats.scraper.fetch import FetchError
from church_stats.storage import ChurchRepository, slugify

runner = CliRunner()


def _fake_scan_url(
    url: str, *, classify: bool = False, classifier_model: str | None = None
) -> ChurchRecord:
    if "bad" in url:
        raise FetchError(f"could not fetch {url}")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    church_id = slugify(urlparse(url).netloc)
    return ChurchRecord(id=church_id, name=url, created_at=now, updated_at=now)


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "DEFAULT_DATA_DIR", tmp_path / "data")


def test_scan_batch_reports_mixed_success_and_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "scan_url", _fake_scan_url)

    urls_file = tmp_path / "urls.txt"
    urls_file.write_text(
        "# a comment, and a blank line below\n"
        "https://good-one.example/\n"
        "\n"
        "https://bad-one.example/\n"
    )

    result = runner.invoke(cli.app, ["scan-batch", str(urls_file)])

    assert result.exit_code == 1
    assert "OK      https://good-one.example/ -> good-one-example" in result.output
    assert "FAILED  https://bad-one.example/: could not fetch https://bad-one.example/" in (
        result.output
    )
    assert "Scanned 2: 1 succeeded, 1 failed." in result.output
    assert (cli.DEFAULT_DATA_DIR / "good-one-example.json").exists()
    assert not (cli.DEFAULT_DATA_DIR / "bad-one-example.json").exists()


def test_scan_batch_no_save_does_not_write_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "scan_url", _fake_scan_url)

    urls_file = tmp_path / "urls.txt"
    urls_file.write_text("https://good-one.example/\n")

    result = runner.invoke(cli.app, ["scan-batch", str(urls_file), "--no-save"])

    assert result.exit_code == 0
    assert not cli.DEFAULT_DATA_DIR.exists()


def test_scan_batch_rejects_empty_file(tmp_path: Path) -> None:
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text("# nothing but comments\n\n")

    result = runner.invoke(cli.app, ["scan-batch", str(urls_file)])

    assert result.exit_code == 1
    assert "No URLs found" in result.output


def test_scan_batch_rejects_invalid_concurrency(tmp_path: Path) -> None:
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text("https://good-one.example/\n")

    result = runner.invoke(cli.app, ["scan-batch", str(urls_file), "--concurrency", "0"])

    assert result.exit_code == 1
    assert "--concurrency must be at least 1" in result.output


def test_scan_merges_into_existing_record_by_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "scan_url", _fake_scan_url)
    repo = ChurchRepository(cli.DEFAULT_DATA_DIR)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repo.save(
        ChurchRecord(
            id="good-one-example",
            name="Old Name",
            notes="Manually added note.",
            created_at=now,
            updated_at=now,
        )
    )

    result = runner.invoke(cli.app, ["scan", "https://good-one.example/"])

    assert result.exit_code == 0, result.output
    merged = repo.load("good-one-example")
    assert merged.name == "https://good-one.example/"  # fresh scrape wins
    assert merged.notes == "Manually added note."  # not clobbered by the re-scan


def test_scan_batch_merges_into_existing_record_by_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "scan_url", _fake_scan_url)
    repo = ChurchRepository(cli.DEFAULT_DATA_DIR)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repo.save(
        ChurchRecord(
            id="good-one-example",
            name="Old Name",
            tags=["visited-in-person"],
            created_at=now,
            updated_at=now,
        )
    )
    urls_file = cli.DEFAULT_DATA_DIR.parent / "urls.txt"
    urls_file.write_text("https://good-one.example/\n")

    result = runner.invoke(cli.app, ["scan-batch", str(urls_file)])

    assert result.exit_code == 0, result.output
    merged = repo.load("good-one-example")
    assert merged.name == "https://good-one.example/"
    assert merged.tags == ["visited-in-person"]


def test_duplicates_reports_likely_pairs() -> None:
    repo = ChurchRepository(cli.DEFAULT_DATA_DIR)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repo.save(ChurchRecord(id="a", name="Grace Community Church", created_at=now, updated_at=now))
    repo.save(ChurchRecord(id="b", name="Grace Community Church", created_at=now, updated_at=now))

    result = runner.invoke(cli.app, ["duplicates"])

    assert result.exit_code == 0, result.output
    assert "a  <->  b" in result.output
    assert "similar name" in result.output


def test_duplicates_reports_none_found() -> None:
    repo = ChurchRepository(cli.DEFAULT_DATA_DIR)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repo.save(ChurchRecord(id="a", name="First Baptist", created_at=now, updated_at=now))
    repo.save(ChurchRecord(id="b", name="St. Mary's Cathedral", created_at=now, updated_at=now))

    result = runner.invoke(cli.app, ["duplicates"])

    assert result.exit_code == 0
    assert "No likely duplicates found." in result.output


def test_merge_command_combines_and_deletes() -> None:
    repo = ChurchRepository(cli.DEFAULT_DATA_DIR)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repo.save(
        ChurchRecord(id="keep", name="Grace Community", phone=None, created_at=now, updated_at=now)
    )
    repo.save(
        ChurchRecord(
            id="drop",
            name="Grace Community Church",
            phone="(555) 123-4567",
            created_at=now,
            updated_at=now,
        )
    )

    result = runner.invoke(cli.app, ["merge", "keep", "drop", "--yes"])

    assert result.exit_code == 0, result.output
    merged = repo.load("keep")
    assert merged.name == "Grace Community"  # keep's own non-empty field wins
    assert merged.phone == "(555) 123-4567"  # filled in from drop
    assert not repo.exists("drop")


def test_merge_command_aborts_without_confirmation() -> None:
    repo = ChurchRepository(cli.DEFAULT_DATA_DIR)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repo.save(ChurchRecord(id="keep", name="Grace Community", created_at=now, updated_at=now))
    repo.save(
        ChurchRecord(id="drop", name="Grace Community Church", created_at=now, updated_at=now)
    )

    result = runner.invoke(cli.app, ["merge", "keep", "drop"], input="n\n")

    assert result.exit_code != 0
    assert repo.exists("keep")
    assert repo.exists("drop")


def test_merge_command_missing_id_errors() -> None:
    repo = ChurchRepository(cli.DEFAULT_DATA_DIR)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repo.save(ChurchRecord(id="keep", name="Grace Community", created_at=now, updated_at=now))

    result = runner.invoke(cli.app, ["merge", "keep", "does-not-exist", "--yes"])

    assert result.exit_code == 1
    assert "No church found with id 'does-not-exist'" in result.output
