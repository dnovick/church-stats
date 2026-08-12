from __future__ import annotations

from pathlib import Path

from church_stats.scraper.extract import extract


def test_extract_from_rich_page(fixtures_dir: Path) -> None:
    html = (fixtures_dir / "sample_church.html").read_text(encoding="utf-8")
    data = extract(html)

    assert data.name == "Grace Community Church"
    assert data.description == "A welcoming congregation in Springfield."
    assert data.phone == "(555) 123-4567"
    assert data.email == "info@gracecommunity.example"
    assert data.street == "123 Main St"
    assert data.city == "Springfield"
    assert data.region == "IL"
    assert data.postal_code == "62701"
    assert data.country == "US"
    assert data.social_links["facebook"] == "https://www.facebook.com/gracecommunity"
    assert data.social_links["instagram"] == "https://www.instagram.com/gracecommunity"
    assert data.social_links["youtube"] == "https://www.youtube.com/gracecommunity"


def test_extract_from_minimal_page_leaves_fields_unset(fixtures_dir: Path) -> None:
    html = (fixtures_dir / "minimal.html").read_text(encoding="utf-8")
    data = extract(html)

    assert data.name == "Untitled Page"
    assert data.description is None
    assert data.phone is None
    assert data.email is None
    assert data.social_links == {}
