from __future__ import annotations

from church_stats.models import ChurchRecord


def test_minimal_record_has_sensible_defaults(sample_record: ChurchRecord) -> None:
    assert sample_record.schema_version == 1
    assert sample_record.also_known_as == []
    assert sample_record.address.city is None
    assert sample_record.social_links.facebook is None


def test_extra_fields_are_allowed() -> None:
    record = ChurchRecord.model_validate(
        {
            "id": "example",
            "name": "Example Church",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "parking_notes": "Lot behind the building",
        }
    )
    assert record.model_dump()["parking_notes"] == "Lot behind the building"


def test_round_trip_through_json(sample_record: ChurchRecord) -> None:
    dumped = sample_record.model_dump_json()
    restored = ChurchRecord.model_validate_json(dumped)
    assert restored == sample_record
