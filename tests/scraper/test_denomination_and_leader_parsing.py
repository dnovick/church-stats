from __future__ import annotations

from church_stats.scraper.extract import (
    ExtractedLeader,
    _extract_denomination,
    _parse_leaders_from_text,
)


def test_denomination_matches_known_alias() -> None:
    text = "We are a proud Southern Baptist congregation serving the community."
    assert _extract_denomination(text) == "Southern Baptist"


def test_denomination_normalizes_hyphenated_and_unhyphenated_nondenominational() -> None:
    assert _extract_denomination("A nondenominational church for all.") == "Non-denominational"
    assert _extract_denomination("A non-denominational church for all.") == "Non-denominational"


def test_denomination_prefers_longest_match() -> None:
    # "presbyterian church in america" should not get cut short by a
    # coincidental partial overlap with another alias.
    text = "We're part of the Presbyterian Church in America."
    assert _extract_denomination(text) == "Presbyterian Church in America"


def test_denomination_returns_none_when_no_known_alias_present() -> None:
    assert _extract_denomination("Welcome to our church! Join us Sunday.") is None


def test_leaders_parses_name_comma_title() -> None:
    leaders = _parse_leaders_from_text("John Smith, Senior Pastor")
    assert leaders == [ExtractedLeader(name="John Smith", title="Senior Pastor")]


def test_leaders_parses_title_colon_name() -> None:
    leaders = _parse_leaders_from_text("Senior Pastor: John Smith")
    assert leaders == [ExtractedLeader(name="John Smith", title="Senior Pastor")]


def test_leaders_parses_multiple_pairs_in_one_block() -> None:
    leaders = _parse_leaders_from_text("John Smith, Senior Pastor, Jane Doe, Worship Pastor")
    assert leaders == [
        ExtractedLeader(name="John Smith", title="Senior Pastor"),
        ExtractedLeader(name="Jane Doe", title="Worship Pastor"),
    ]


def test_leaders_prefers_longer_title_match_over_generic_pastor() -> None:
    leaders = _parse_leaders_from_text("Maria Gonzalez, Executive Pastor")
    assert leaders == [ExtractedLeader(name="Maria Gonzalez", title="Executive Pastor")]


def test_leaders_ignores_unrelated_comma_separated_text() -> None:
    # No title keyword follows the comma, so this must not be misread as a
    # leader -- "John" alone isn't a confident enough anchor.
    text = "Welcome to our church, John, we are glad you visited on Sunday."
    assert _parse_leaders_from_text(text) == []


def test_leaders_requires_capitalized_name_like_tokens() -> None:
    # A title keyword followed by lowercase, non-name-like text shouldn't
    # be mistaken for a person's name.
    assert _parse_leaders_from_text("Pastor: our new hire starts soon") == []
