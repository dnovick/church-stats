"""Orchestrates fetch -> extract -> ChurchRecord construction."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from pydantic import HttpUrl

from church_stats.models import Address, ChurchRecord, ServiceTime, SocialLinks, SourceRecord
from church_stats.scraper.extract import ExtractedData, extract
from church_stats.scraper.fetch import fetch_page
from church_stats.storage import slugify


def _record_id_from_url(url: str) -> str:
    host = urlparse(url).netloc or url
    return slugify(host)


def _optional_url(value: str | None) -> HttpUrl | None:
    return HttpUrl(value) if value else None


def _build_record(url: str, data: ExtractedData, *, fetched_at: datetime) -> ChurchRecord:
    now = fetched_at
    return ChurchRecord(
        id=_record_id_from_url(url),
        name=data.name or url,
        website=HttpUrl(url),
        description=data.description,
        address=Address(
            street=data.street,
            city=data.city,
            region=data.region,
            postal_code=data.postal_code,
            country=data.country,
        ),
        phone=data.phone,
        email=data.email,
        service_times=[
            ServiceTime(
                name=service_time.name,
                day_of_week=service_time.day_of_week,
                time=service_time.time,
                language=service_time.language,
            )
            for service_time in data.service_times
        ],
        social_links=SocialLinks(
            facebook=_optional_url(data.social_links.get("facebook")),
            instagram=_optional_url(data.social_links.get("instagram")),
            youtube=_optional_url(data.social_links.get("youtube")),
            x=_optional_url(data.social_links.get("x")),
        ),
        sources=[SourceRecord(url=HttpUrl(url), fetched_at=fetched_at, method="scraped")],
        created_at=now,
        updated_at=now,
    )


def scan_url(url: str) -> ChurchRecord:
    """Fetch ``url``, extract best-effort church data, and build a ``ChurchRecord``.

    Does not save the record; the caller decides whether/where to persist it.
    """
    html = fetch_page(url)
    data = extract(html)
    fetched_at = datetime.now(timezone.utc)
    return _build_record(url, data, fetched_at=fetched_at)
