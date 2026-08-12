"""File-based storage for church records: one JSON file per church."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from church_stats.models import ChurchRecord


def slugify(text: str) -> str:
    """Turn arbitrary text (e.g. a domain or church name) into a filesystem-safe id."""
    slug = text.strip().lower()
    slug = re.sub(r"^https?://", "", slug)
    slug = re.sub(r"^www\.", "", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


class ChurchNotFoundError(KeyError):
    """Raised when a requested church id has no stored record."""


class ChurchRepository:
    """Reads and writes ``ChurchRecord`` JSON files under a data directory."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    def _path_for(self, church_id: str) -> Path:
        return self.data_dir / f"{church_id}.json"

    def exists(self, church_id: str) -> bool:
        return self._path_for(church_id).is_file()

    def unique_id(self, base_id: str) -> str:
        """Return ``base_id``, or ``base_id-2``, ``base_id-3``, ... if taken."""
        if not self.exists(base_id):
            return base_id
        suffix = 2
        while self.exists(f"{base_id}-{suffix}"):
            suffix += 1
        return f"{base_id}-{suffix}"

    def save(self, record: ChurchRecord) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self._path_for(record.id)
        path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path

    def load(self, church_id: str) -> ChurchRecord:
        path = self._path_for(church_id)
        if not path.is_file():
            raise ChurchNotFoundError(church_id)
        return ChurchRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def list_ids(self) -> list[str]:
        if not self.data_dir.is_dir():
            return []
        return sorted(p.stem for p in self.data_dir.glob("*.json"))

    def all(self) -> Iterator[ChurchRecord]:
        for church_id in self.list_ids():
            yield self.load(church_id)
