"""Orchestrates fetch -> extract -> ChurchRecord construction."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from pydantic import HttpUrl

from church_stats.models import (
    Address,
    ChurchRecord,
    Leader,
    ServiceTime,
    SocialLinks,
    SourceRecord,
)
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
        denomination=data.denomination,
        also_known_as=data.also_known_as,
        address=Address(
            street=data.street,
            city=data.city,
            region=data.region,
            postal_code=data.postal_code,
            country=data.country,
        ),
        phone=data.phone,
        email=data.email,
        leaders=[Leader(name=leader.name, title=leader.title) for leader in data.leaders],
        service_times=[
            ServiceTime(
                name=service_time.name,
                day_of_week=service_time.day_of_week,
                time=service_time.time,
                language=service_time.language,
                raw_text=service_time.raw_text,
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


def scan_url(
    url: str, *, classify: bool = False, classifier_model: str | None = None
) -> ChurchRecord:
    """Fetch ``url``, extract best-effort church data, and build a ``ChurchRecord``.

    Does not save the record; the caller decides whether/where to persist it.
    Set ``classify=True`` to also classify the page's outreach messaging via
    the Claude API (requires the ``classify`` optional dependency group and
    Anthropic credentials).
    """
    html = fetch_page(url)
    data = extract(html)
    fetched_at = datetime.now(timezone.utc)
    record = _build_record(url, data, fetched_at=fetched_at)

    if classify:
        from church_stats.classifier.messaging import (
            DEFAULT_CLASSIFIER_MODEL,
            classify_messaging,
        )

        messaging = classify_messaging(
            data.page_text, model=classifier_model or DEFAULT_CLASSIFIER_MODEL
        )
        record = record.model_copy(update={"messaging": messaging})

    return record
