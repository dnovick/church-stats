"""File-based storage for church records: one JSON file per church."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import TypeVar

from church_stats.models import Address, ChurchRecord, SocialLinks

T = TypeVar("T")


def slugify(text: str) -> str:
    """Turn arbitrary text (e.g. a domain or church name) into a filesystem-safe id."""
    slug = text.strip().lower()
    slug = re.sub(r"^https?://", "", slug)
    slug = re.sub(r"^www\.", "", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _prefer_non_empty(existing: T, incoming: T) -> T:
    """Prefer ``incoming`` unless it's ``None`` or an empty string."""
    if incoming is None:
        return existing
    if isinstance(incoming, str) and incoming == "":
        return existing
    return incoming


def _merge_address(existing: Address, incoming: Address) -> Address:
    return Address(
        street=_prefer_non_empty(existing.street, incoming.street),
        city=_prefer_non_empty(existing.city, incoming.city),
        region=_prefer_non_empty(existing.region, incoming.region),
        postal_code=_prefer_non_empty(existing.postal_code, incoming.postal_code),
        country=_prefer_non_empty(existing.country, incoming.country),
        latitude=_prefer_non_empty(existing.latitude, incoming.latitude),
        longitude=_prefer_non_empty(existing.longitude, incoming.longitude),
    )


def _merge_social_links(existing: SocialLinks, incoming: SocialLinks) -> SocialLinks:
    return SocialLinks(
        facebook=_prefer_non_empty(existing.facebook, incoming.facebook),
        instagram=_prefer_non_empty(existing.instagram, incoming.instagram),
        youtube=_prefer_non_empty(existing.youtube, incoming.youtube),
        x=_prefer_non_empty(existing.x, incoming.x),
        other={**existing.other, **incoming.other},
    )


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

    def delete(self, church_id: str) -> None:
        path = self._path_for(church_id)
        if not path.is_file():
            raise ChurchNotFoundError(church_id)
        path.unlink()

    def merge(self, existing: ChurchRecord, incoming: ChurchRecord) -> ChurchRecord:
        """Merge ``incoming`` into ``existing``, returning the merged record.

        Prefers ``incoming`` values only where they're non-empty, so this
        can't silently erase data a site temporarily stopped exposing.
        Fields the scraper never touches (``notes``, ``tags``) come along
        for free via ``model_copy`` since they're never in ``update``, so
        manual edits to those always survive a re-scan. Sources accumulate;
        list fields (``service_times``, ``leaders``, ``also_known_as``) are
        replaced wholesale when the new scan found any, so stale entries
        don't linger next to fresh ones.
        """
        update = {
            "name": _prefer_non_empty(existing.name, incoming.name),
            "website": _prefer_non_empty(existing.website, incoming.website),
            "description": _prefer_non_empty(existing.description, incoming.description),
            "denomination": _prefer_non_empty(existing.denomination, incoming.denomination),
            "also_known_as": incoming.also_known_as or existing.also_known_as,
            "address": _merge_address(existing.address, incoming.address),
            "phone": _prefer_non_empty(existing.phone, incoming.phone),
            "email": _prefer_non_empty(existing.email, incoming.email),
            "leaders": incoming.leaders or existing.leaders,
            "service_times": incoming.service_times or existing.service_times,
            "social_links": _merge_social_links(existing.social_links, incoming.social_links),
            "sources": existing.sources + incoming.sources,
            "messaging": incoming.messaging or existing.messaging,
            "updated_at": incoming.updated_at,
        }
        return existing.model_copy(update=update)

    def list_ids(self) -> list[str]:
        if not self.data_dir.is_dir():
            return []
        return sorted(p.stem for p in self.data_dir.glob("*.json"))

    def all(self) -> Iterator[ChurchRecord]:
        for church_id in self.list_ids():
            yield self.load(church_id)
