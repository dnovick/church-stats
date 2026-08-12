from __future__ import annotations

from pathlib import Path

import pytest

from church_stats.models import ChurchRecord
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
