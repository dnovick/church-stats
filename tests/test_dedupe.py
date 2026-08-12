from __future__ import annotations

from datetime import datetime, timezone

from church_stats.dedupe import find_duplicates
from church_stats.models import Address, ChurchRecord

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _record(**overrides: object) -> ChurchRecord:
    defaults: dict[str, object] = {
        "id": "some-id",
        "name": "Some Church",
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(overrides)
    return ChurchRecord.model_validate(defaults)


def test_finds_duplicate_by_similar_name() -> None:
    a = _record(id="grace-community", name="Grace Community Church")
    b = _record(id="grace-community-church-of-springfield", name="Grace Community Church")

    candidates = find_duplicates([a, b])

    assert len(candidates) == 1
    assert candidates[0].first_id == "grace-community"
    assert candidates[0].second_id == "grace-community-church-of-springfield"
    assert any("similar name" in reason for reason in candidates[0].reasons)


def test_finds_duplicate_by_matching_phone() -> None:
    a = _record(id="a", name="First Baptist", phone="(555) 123-4567")
    b = _record(id="b", name="Totally Different Name", phone="555.123.4567")

    candidates = find_duplicates([a, b])

    assert len(candidates) == 1
    assert any("matching phone" in reason for reason in candidates[0].reasons)


def test_finds_duplicate_by_same_location_and_weak_name_match() -> None:
    a = _record(
        id="a",
        name="Grace Fellowship",
        address=Address(city="Springfield", region="IL"),
    )
    b = _record(
        id="b",
        name="Grace Church",
        address=Address(city="Springfield", region="IL"),
    )

    candidates = find_duplicates([a, b])

    assert len(candidates) == 1
    assert any("same city/region" in reason for reason in candidates[0].reasons)


def test_no_duplicate_for_unrelated_churches() -> None:
    a = _record(
        id="a",
        name="First Baptist Church",
        phone="(555) 111-1111",
        address=Address(city="Springfield", region="IL"),
    )
    b = _record(
        id="b",
        name="St. Mary's Cathedral",
        phone="(555) 999-9999",
        address=Address(city="Portland", region="OR"),
    )

    assert find_duplicates([a, b]) == []


def test_pairwise_compares_all_records() -> None:
    a = _record(id="a", name="Grace Church")
    b = _record(id="b", name="Grace Church")
    c = _record(id="c", name="Totally Unrelated Name")

    candidates = find_duplicates([a, b, c])

    pairs = {(c.first_id, c.second_id) for c in candidates}
    assert pairs == {("a", "b")}
