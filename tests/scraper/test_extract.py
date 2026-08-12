from __future__ import annotations

from pathlib import Path

from church_stats.scraper.extract import ExtractedLeader, extract


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
    assert data.also_known_as == ["Grace Fellowship"]
    assert data.denomination == "Southern Baptist"
    assert data.leaders == [ExtractedLeader(name="Rev. Maria Gonzalez", title="Senior Pastor")]

    assert "Grace Community Church" in data.page_text
    assert "Join us Sundays!" in data.page_text
    # Footer boilerplate is stripped out of the classifier-facing text.
    assert "Facebook" not in data.page_text


def test_extract_from_minimal_page_leaves_fields_unset(fixtures_dir: Path) -> None:
    html = (fixtures_dir / "minimal.html").read_text(encoding="utf-8")
    data = extract(html)

    assert data.name == "Untitled Page"
    assert data.description is None
    assert data.phone is None
    assert data.email is None
    assert data.social_links == {}
    assert data.service_times == []
    assert data.also_known_as == []
    assert data.denomination is None
    assert data.leaders == []


def test_extract_handles_graph_wrapped_jsonld_and_opening_hours(fixtures_dir: Path) -> None:
    html = (fixtures_dir / "graph_and_hours.html").read_text(encoding="utf-8")
    data = extract(html)

    assert data.name == "River City Church"
    assert data.phone == "(555) 987-6543"
    assert data.city == "Rivertown"

    service_times = {(st.name, st.day_of_week, st.time) for st in data.service_times}
    assert service_times == {
        ("Sunday Worship", "Sunday", "09:00"),
        ("Second Service", "Sunday", "11:00"),
        ("Midweek Bible Study", "Wednesday", "19:00"),
    }


def test_extract_merges_multiple_jsonld_entries_and_dedupes_service_times(
    fixtures_dir: Path,
) -> None:
    html = (fixtures_dir / "multiple_jsonld.html").read_text(encoding="utf-8")
    data = extract(html)

    # First entry wins for name/phone; second entry fills in address, which the
    # first entry didn't have.
    assert data.name == "Hilltop Chapel"
    assert data.phone == "(555) 111-2222"
    assert data.city == "Hilltown"

    # Both entries describe the same Sunday service; it should appear once.
    assert len(data.service_times) == 1
    assert data.service_times[0].name == "Sunday Service"
    assert data.service_times[0].day_of_week == "Sunday"
    assert data.service_times[0].time == "10:00"
    # Structured JSON-LD hours don't need a raw-text fallback.
    assert data.service_times[0].raw_text is None


def test_extract_falls_back_to_free_text_service_times_without_jsonld(
    fixtures_dir: Path,
) -> None:
    html = (fixtures_dir / "free_text_service_times.html").read_text(encoding="utf-8")
    data = extract(html)

    parsed = {(st.day_of_week, st.time, st.language) for st in data.service_times}
    assert parsed == {
        ("Sunday", "09:00", None),
        ("Sunday", "11:00", None),
        ("Saturday", "17:00", "Spanish"),
    }
    assert all(st.raw_text for st in data.service_times)


def test_extract_prefers_jsonld_service_times_over_free_text(fixtures_dir: Path) -> None:
    # sample_church.html has both JSON-LD (no hours) and free text ("Join us
    # Sundays!" with no parseable time) -- neither should produce a bogus
    # service time, and this also confirms the free-text fallback only
    # engages when JSON-LD found nothing, not whenever JSON-LD is present.
    html = (fixtures_dir / "graph_and_hours.html").read_text(encoding="utf-8")
    data = extract(html)

    assert data.service_times
    assert all(st.raw_text is None for st in data.service_times)


def test_extract_falls_back_to_free_text_leaders_without_jsonld(fixtures_dir: Path) -> None:
    html = (fixtures_dir / "leadership_free_text.html").read_text(encoding="utf-8")
    data = extract(html)

    assert data.leaders == [
        ExtractedLeader(name="John Carter", title="Senior Pastor"),
        ExtractedLeader(name="Amelia Cross", title="Worship Pastor"),
    ]


def test_extract_prefers_jsonld_leaders_over_free_text(fixtures_dir: Path) -> None:
    html = (fixtures_dir / "sample_church.html").read_text(encoding="utf-8")
    data = extract(html)

    # sample_church.html has no "Meet the Team"-style heading, so this also
    # confirms the JSON-LD founder is what's actually driving the result.
    assert data.leaders == [ExtractedLeader(name="Rev. Maria Gonzalez", title="Senior Pastor")]
