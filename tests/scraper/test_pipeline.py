from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from church_stats.classifier import messaging as messaging_module
from church_stats.models import Leader, MessagingClassification
from church_stats.scraper import pipeline
from church_stats.scraper.fetch import FetchError


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
    assert record.also_known_as == ["Grace Fellowship"]
    assert record.denomination == "Southern Baptist"
    assert record.leaders == [Leader(name="Rev. Maria Gonzalez", title="Senior Pastor")]


def test_scan_url_maps_extracted_service_times(
    fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    html = (fixtures_dir / "graph_and_hours.html").read_text(encoding="utf-8")
    monkeypatch.setattr(pipeline, "fetch_page", lambda url: html)

    record = pipeline.scan_url("https://www.rivercitychurch.example/")

    assert len(record.service_times) == 3
    assert {st.day_of_week for st in record.service_times} == {"Sunday", "Wednesday"}


def test_scan_url_with_classify_attaches_messaging(
    fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    html = (fixtures_dir / "sample_church.html").read_text(encoding="utf-8")
    monkeypatch.setattr(pipeline, "fetch_page", lambda url: html)

    fake_classification = MessagingClassification(
        theme="spiritual_encounter",
        confidence=0.8,
        evidence="join us for worship",
        model="claude-haiku-4-5",
        classified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(
        messaging_module, "classify_messaging", lambda text, model: fake_classification
    )

    record = pipeline.scan_url("https://www.gracecommunity.example/", classify=True)

    assert record.messaging == fake_classification


def test_scan_url_crawls_staff_link_to_find_leaders(
    fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    homepage_html = (fixtures_dir / "homepage_with_staff_link.html").read_text(encoding="utf-8")
    staff_html = (fixtures_dir / "leadership_free_text.html").read_text(encoding="utf-8")

    def fake_fetch_page(url: str) -> str:
        return staff_html if url.endswith("/staff") else homepage_html

    monkeypatch.setattr(pipeline, "fetch_page", fake_fetch_page)

    record = pipeline.scan_url("https://www.hilltop.example/")

    assert record.leaders == [
        Leader(name="John Carter", title="Senior Pastor"),
        Leader(name="Amelia Cross", title="Worship Pastor"),
    ]
    # The homepage and the crawled staff page both get their own source.
    assert [str(s.url) for s in record.sources] == [
        "https://www.hilltop.example/",
        "https://www.hilltop.example/staff",
    ]


def test_scan_url_with_crawl_false_skips_related_pages(
    fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    homepage_html = (fixtures_dir / "homepage_with_staff_link.html").read_text(encoding="utf-8")
    fetch_calls: list[str] = []

    def fake_fetch_page(url: str) -> str:
        fetch_calls.append(url)
        return homepage_html

    monkeypatch.setattr(pipeline, "fetch_page", fake_fetch_page)

    record = pipeline.scan_url("https://www.hilltop.example/", crawl=False)

    assert record.leaders == []
    assert fetch_calls == ["https://www.hilltop.example/"]


def test_scan_url_crawl_survives_a_failed_related_page_fetch(
    fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    homepage_html = (fixtures_dir / "homepage_with_staff_link.html").read_text(encoding="utf-8")

    def fake_fetch_page(url: str) -> str:
        if url.endswith("/staff"):
            raise FetchError("boom")
        return homepage_html

    monkeypatch.setattr(pipeline, "fetch_page", fake_fetch_page)

    record = pipeline.scan_url("https://www.hilltop.example/")

    assert record.leaders == []
    assert [str(s.url) for s in record.sources] == ["https://www.hilltop.example/"]
