from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import HttpUrl

from church_stats.models import (
    Address,
    ChurchRecord,
    MessagingClassification,
    ServiceTime,
    SocialLinks,
    SourceRecord,
)
from church_stats.storage import ChurchNotFoundError, ChurchRepository, slugify


def test_slugify_strips_scheme_and_www() -> None:
    assert slugify("https://www.Grace-Community.example/") == "grace-community-example"


def test_save_and_load_round_trip(tmp_path: Path, sample_record: ChurchRecord) -> None:
    repo = ChurchRepository(tmp_path)
    path = repo.save(sample_record)

    assert path == tmp_path / "grace-community.json"
    loaded = repo.load("grace-community")
    assert loaded == sample_record


def test_load_missing_church_raises(tmp_path: Path) -> None:
    repo = ChurchRepository(tmp_path)
    with pytest.raises(ChurchNotFoundError):
        repo.load("does-not-exist")


def test_list_ids_and_all(tmp_path: Path, sample_record: ChurchRecord) -> None:
    repo = ChurchRepository(tmp_path)
    repo.save(sample_record)
    other = sample_record.model_copy(update={"id": "other-church", "name": "Other Church"})
    repo.save(other)

    assert repo.list_ids() == ["grace-community", "other-church"]
    assert {record.id for record in repo.all()} == {"grace-community", "other-church"}


def test_unique_id_disambiguates_on_collision(tmp_path: Path, sample_record: ChurchRecord) -> None:
    repo = ChurchRepository(tmp_path)
    repo.save(sample_record)
    assert repo.unique_id("grace-community") == "grace-community-2"
    assert repo.unique_id("brand-new") == "brand-new"


def test_delete_removes_record(tmp_path: Path, sample_record: ChurchRecord) -> None:
    repo = ChurchRepository(tmp_path)
    repo.save(sample_record)
    repo.delete("grace-community")
    assert not repo.exists("grace-community")


def test_delete_missing_church_raises(tmp_path: Path) -> None:
    repo = ChurchRepository(tmp_path)
    with pytest.raises(ChurchNotFoundError):
        repo.delete("does-not-exist")


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
LATER = datetime(2026, 2, 1, tzinfo=timezone.utc)


def test_merge_prefers_non_empty_incoming_scraped_fields(tmp_path: Path) -> None:
    repo = ChurchRepository(tmp_path)
    existing = ChurchRecord(
        id="grace-community",
        name="Grace Community",
        phone="(555) 111-2222",
        created_at=NOW,
        updated_at=NOW,
    )
    incoming = ChurchRecord(
        id="grace-community",
        name="Grace Community Church",
        phone=None,
        created_at=LATER,
        updated_at=LATER,
    )

    merged = repo.merge(existing, incoming)

    assert merged.name == "Grace Community Church"  # non-empty incoming wins
    assert merged.phone == "(555) 111-2222"  # empty incoming -> keep existing
    assert merged.created_at == NOW  # created_at is not touched by merge
    assert merged.updated_at == LATER  # updated_at always takes incoming


def test_merge_preserves_manually_added_fields(tmp_path: Path) -> None:
    repo = ChurchRepository(tmp_path)
    existing = ChurchRecord(
        id="grace-community",
        name="Grace Community",
        denomination="Baptist",
        notes="Called ahead, very welcoming.",
        tags=["large", "contemporary"],
        created_at=NOW,
        updated_at=NOW,
    )
    incoming = ChurchRecord(
        id="grace-community", name="Grace Community", created_at=LATER, updated_at=LATER
    )

    merged = repo.merge(existing, incoming)

    assert merged.denomination == "Baptist"
    assert merged.notes == "Called ahead, very welcoming."
    assert merged.tags == ["large", "contemporary"]


def test_merge_preserves_extra_fields(tmp_path: Path) -> None:
    repo = ChurchRepository(tmp_path)
    existing = ChurchRecord.model_validate(
        {
            "id": "grace-community",
            "name": "Grace Community",
            "created_at": NOW.isoformat(),
            "updated_at": NOW.isoformat(),
            "parking_notes": "Lot behind the building",
        }
    )
    incoming = ChurchRecord(
        id="grace-community", name="Grace Community", created_at=LATER, updated_at=LATER
    )

    merged = repo.merge(existing, incoming)

    assert merged.model_dump()["parking_notes"] == "Lot behind the building"


def test_merge_accumulates_sources(tmp_path: Path) -> None:
    repo = ChurchRepository(tmp_path)
    existing = ChurchRecord(
        id="grace-community",
        name="Grace Community",
        sources=[SourceRecord(url=HttpUrl("https://a.example/"), fetched_at=NOW, method="scraped")],
        created_at=NOW,
        updated_at=NOW,
    )
    incoming = ChurchRecord(
        id="grace-community",
        name="Grace Community",
        sources=[
            SourceRecord(url=HttpUrl("https://b.example/"), fetched_at=LATER, method="scraped")
        ],
        created_at=LATER,
        updated_at=LATER,
    )

    merged = repo.merge(existing, incoming)

    assert [str(s.url) for s in merged.sources] == ["https://a.example/", "https://b.example/"]


def test_merge_replaces_service_times_when_incoming_has_any(tmp_path: Path) -> None:
    repo = ChurchRepository(tmp_path)
    existing = ChurchRecord(
        id="grace-community",
        name="Grace Community",
        service_times=[ServiceTime(name="Old Sunday Service", day_of_week="Sunday", time="09:00")],
        created_at=NOW,
        updated_at=NOW,
    )
    incoming = ChurchRecord(
        id="grace-community",
        name="Grace Community",
        service_times=[ServiceTime(name="Sunday Worship", day_of_week="Sunday", time="10:00")],
        created_at=LATER,
        updated_at=LATER,
    )

    merged = repo.merge(existing, incoming)

    assert merged.service_times == incoming.service_times


def test_merge_keeps_existing_service_times_when_incoming_has_none(tmp_path: Path) -> None:
    repo = ChurchRepository(tmp_path)
    existing = ChurchRecord(
        id="grace-community",
        name="Grace Community",
        service_times=[ServiceTime(name="Sunday Worship", day_of_week="Sunday", time="09:00")],
        created_at=NOW,
        updated_at=NOW,
    )
    incoming = ChurchRecord(
        id="grace-community", name="Grace Community", created_at=LATER, updated_at=LATER
    )

    merged = repo.merge(existing, incoming)

    assert merged.service_times == existing.service_times


def test_merge_messaging_prefers_incoming_but_keeps_existing_if_absent(tmp_path: Path) -> None:
    repo = ChurchRepository(tmp_path)
    classification = MessagingClassification(
        theme="community_belonging",
        confidence=0.9,
        evidence="find your people",
        model="claude-haiku-4-5",
        classified_at=NOW,
    )
    existing = ChurchRecord(
        id="grace-community",
        name="Grace Community",
        messaging=classification,
        created_at=NOW,
        updated_at=NOW,
    )
    incoming = ChurchRecord(
        id="grace-community", name="Grace Community", created_at=LATER, updated_at=LATER
    )

    # A re-scan without --classify shouldn't erase a prior classification.
    assert repo.merge(existing, incoming).messaging == classification

    # But a fresh classification on the incoming scan should win.
    new_classification = classification.model_copy(update={"theme": "outreach_service"})
    incoming_with_classification = incoming.model_copy(update={"messaging": new_classification})
    assert repo.merge(existing, incoming_with_classification).messaging == new_classification


def test_merge_address_and_social_links_field_by_field(tmp_path: Path) -> None:
    repo = ChurchRepository(tmp_path)
    existing = ChurchRecord(
        id="grace-community",
        name="Grace Community",
        address=Address(street="123 Main St", city="Springfield"),
        social_links=SocialLinks(facebook=HttpUrl("https://www.facebook.com/gracecommunity")),
        created_at=NOW,
        updated_at=NOW,
    )
    incoming = ChurchRecord(
        id="grace-community",
        name="Grace Community",
        address=Address(city="Springfield", region="IL"),
        social_links=SocialLinks(instagram=HttpUrl("https://www.instagram.com/gracecommunity")),
        created_at=LATER,
        updated_at=LATER,
    )

    merged = repo.merge(existing, incoming)

    assert merged.address.street == "123 Main St"  # only on existing -> kept
    assert merged.address.city == "Springfield"  # both agree
    assert merged.address.region == "IL"  # only on incoming -> filled in
    assert str(merged.social_links.facebook) == "https://www.facebook.com/gracecommunity"
    assert str(merged.social_links.instagram) == "https://www.instagram.com/gracecommunity"
