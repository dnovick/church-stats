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
from church_stats.scraper.extract import ExtractedData, extract, find_related_page_links
from church_stats.scraper.fetch import FetchError, fetch_page
from church_stats.storage import slugify


def _record_id_from_url(url: str) -> str:
    host = urlparse(url).netloc or url
    return slugify(host)


def _optional_url(value: str | None) -> HttpUrl | None:
    return HttpUrl(value) if value else None


def _build_record(
    url: str, data: ExtractedData, *, fetched_at: datetime, sources: list[SourceRecord]
) -> ChurchRecord:
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
        sources=sources,
        created_at=now,
        updated_at=now,
    )


def _crawl_related_pages(url: str, html: str, data: ExtractedData) -> list[SourceRecord]:
    """Best-effort fetch of a same-domain staff/about page to backfill
    ``leaders``/``also_known_as`` when the homepage didn't have them.

    A failed fetch of a related page is skipped rather than failing the
    whole scan. Returns a ``SourceRecord`` for each page actually fetched.
    """
    extra_sources: list[SourceRecord] = []
    if data.leaders and data.also_known_as:
        return extra_sources

    for page_url in find_related_page_links(html, url).values():
        if data.leaders and data.also_known_as:
            break
        try:
            extra_html = fetch_page(page_url)
        except FetchError:
            continue
        extra_sources.append(
            SourceRecord(
                url=HttpUrl(page_url), fetched_at=datetime.now(timezone.utc), method="scraped"
            )
        )
        extra_data = extract(extra_html)
        if not data.leaders:
            data.leaders = extra_data.leaders
        if not data.also_known_as:
            data.also_known_as = extra_data.also_known_as

    return extra_sources


def scan_url(
    url: str,
    *,
    classify: bool = False,
    classifier_model: str | None = None,
    crawl: bool = True,
) -> ChurchRecord:
    """Fetch ``url``, extract best-effort church data, and build a ``ChurchRecord``.

    Does not save the record; the caller decides whether/where to persist it.
    Set ``classify=True`` to also classify the page's outreach messaging via
    the Claude API (requires the ``classify`` optional dependency group and
    Anthropic credentials). Set ``crawl=False`` to skip following same-domain
    staff/about links when ``leaders``/``also_known_as`` come up empty --
    faster, but less likely to find them (see ``_crawl_related_pages``).
    """
    html = fetch_page(url)
    data = extract(html)
    fetched_at = datetime.now(timezone.utc)
    sources = [SourceRecord(url=HttpUrl(url), fetched_at=fetched_at, method="scraped")]

    if crawl:
        sources.extend(_crawl_related_pages(url, html, data))

    record = _build_record(url, data, fetched_at=fetched_at, sources=sources)

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
