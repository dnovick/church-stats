from __future__ import annotations

from church_stats.scraper.extract import _parse_service_times_from_text


def test_parses_two_times_sharing_am_marker() -> None:
    times = _parse_service_times_from_text("Sundays 9am & 11am")

    assert [(t.day_of_week, t.time, t.language) for t in times] == [
        ("Sunday", "09:00", None),
        ("Sunday", "11:00", None),
    ]


def test_forward_fills_meridiem_across_a_time_list() -> None:
    # The leading "9:00" has no meridiem of its own -- it should inherit
    # "AM" from the trailing "11:00 AM", a common church-site shorthand.
    times = _parse_service_times_from_text("Sun 9:00 / 11:00 AM")

    assert [t.time for t in times] == ["09:00", "11:00"]


def test_parses_language_hint_in_parentheses() -> None:
    times = _parse_service_times_from_text("Saturday 5pm (Spanish)")

    assert len(times) == 1
    assert times[0].day_of_week == "Saturday"
    assert times[0].time == "17:00"
    assert times[0].language == "Spanish"


def test_noon_and_midnight_are_handled_correctly() -> None:
    times = _parse_service_times_from_text("Sunday 12pm and 12am")

    assert [t.time for t in times] == ["12:00", "00:00"]


def test_dotted_meridiem_is_accepted() -> None:
    times = _parse_service_times_from_text("Saturdays at 5:30 p.m.")

    assert [t.time for t in times] == ["17:30"]


def test_day_with_no_parseable_time_falls_back_to_raw_text_when_block_has_a_real_time() -> None:
    # "Wednesday evening" alone has no time, but the block is validated by
    # the Sunday entry resolving a real time, so Wednesday's raw text is
    # still worth keeping rather than dropping silently.
    times = _parse_service_times_from_text("Sunday 9am, Wednesday evening Bible study")

    assert [(t.day_of_week, t.time) for t in times] == [("Sunday", "09:00"), ("Wednesday", None)]
    assert times[1].raw_text == "Wednesday evening Bible study"


def test_block_with_no_resolved_time_anywhere_is_discarded() -> None:
    # A day name with zero time evidence anywhere in the block is too weak
    # a signal -- day names show up in plenty of unrelated page content.
    assert _parse_service_times_from_text("Wednesday evening Bible study") == []


def test_multiple_days_in_one_string_are_segmented_independently() -> None:
    times = _parse_service_times_from_text("Sat 5pm (Spanish), Sun 9am & 11am")

    assert [(t.day_of_week, t.time, t.language) for t in times] == [
        ("Saturday", "17:00", "Spanish"),
        ("Sunday", "09:00", None),
        ("Sunday", "11:00", None),
    ]


def test_no_day_mentioned_yields_no_service_times() -> None:
    assert _parse_service_times_from_text("Join us for coffee at 9am!") == []


def test_bare_numbers_without_am_pm_or_colon_are_not_treated_as_times() -> None:
    # "3" here is a room number, not a time -- there's no colon or am/pm to
    # anchor it, so it shouldn't be parsed as a time. With no resolved time
    # anywhere in the block, the whole thing is discarded as too weak a
    # signal (see test_block_with_no_resolved_time_anywhere_is_discarded).
    assert _parse_service_times_from_text("Sunday classes meet in room 3") == []
