from __future__ import annotations

from pathlib import Path

import pytest

from church_stats.scraper import pipeline


def test_scan_url_builds_record_from_fetched_html(
    fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    html = (fixtures_dir / "sample_church.html").read_text(encoding="utf-8")
    monkeypatch.setattr(pipeline, "fetch_page", lambda url: html)

    record = pipeline.scan_url("https://www.gracecommunity.example/")

    assert record.id == "gracecommunity-example"
    assert record.name == "Grace Community Church"
    assert str(record.website) == "https://www.gracecommunity.example/"
    assert record.address.city == "Springfield"
    assert record.phone == "(555) 123-4567"
    assert record.sources[0].method == "scraped"
    assert str(record.sources[0].url) == "https://www.gracecommunity.example/"
