from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from church_stats.classifier import messaging as messaging_module
from church_stats.models import Leader, MessagingClassification
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
