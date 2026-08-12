from __future__ import annotations

from church_stats.scraper.extract import find_related_page_links

_NAV_HTML = """
<html><body>
<nav>
  <a href="/">Home</a>
  <a href="/staff">Staff</a>
  <a href="/about">About</a>
  <a href="https://facebook.com/ourchurch">Facebook</a>
</nav>
</body></html>
"""


def test_finds_staff_and_about_links_and_resolves_relative_urls() -> None:
    links = find_related_page_links(_NAV_HTML, "https://example.org/")

    assert links == {
        "staff": "https://example.org/staff",
        "about": "https://example.org/about",
    }


def test_skips_off_domain_links() -> None:
    html = '<a href="https://otherdomain.example/staff">Staff</a>'
    assert find_related_page_links(html, "https://example.org/") == {}


def test_matches_bare_team_and_leadership_link_text() -> None:
    html = """
    <a href="/team">Team</a>
    <a href="/leadership">Leadership</a>
    """
    links = find_related_page_links(html, "https://example.org/")
    assert links["staff"] == "https://example.org/team"


def test_no_matching_links_returns_empty_dict() -> None:
    html = '<a href="/give">Give</a><a href="/watch">Watch Online</a>'
    assert find_related_page_links(html, "https://example.org/") == {}


def test_absolute_href_on_same_domain_is_kept_as_is() -> None:
    html = '<a href="https://example.org/our-staff">Our Staff</a>'
    links = find_related_page_links(html, "https://example.org/visit")
    assert links["staff"] == "https://example.org/our-staff"
