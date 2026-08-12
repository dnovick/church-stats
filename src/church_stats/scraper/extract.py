"""Heuristic extraction of church data from a page's HTML.

Extraction is best-effort: any field we can't confidently find is left unset
rather than guessed. ``schema.org`` JSON-LD (when present) is the most
reliable source and is preferred over regex/meta-tag heuristics.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup
from bs4.element import Tag

_PHONE_RE = re.compile(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

_SOCIAL_DOMAINS = {
    "facebook.com": "facebook",
    "instagram.com": "instagram",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "x.com": "x",
    "twitter.com": "x",
}

_CHURCH_JSONLD_TYPES = {"church", "localbusiness", "place", "religiousorganization"}


@dataclass
class ExtractedServiceTime:
    name: str | None = None
    day_of_week: str | None = None
    time: str | None = None
    language: str | None = None


@dataclass
class ExtractedData:
    name: str | None = None
    description: str | None = None
    phone: str | None = None
    email: str | None = None
    street: str | None = None
    city: str | None = None
    region: str | None = None
    postal_code: str | None = None
    country: str | None = None
    social_links: dict[str, str] = field(default_factory=dict)
    service_times: list[ExtractedServiceTime] = field(default_factory=list)


def _meta_content(
    soup: BeautifulSoup, *, property_: str | None = None, name: str | None = None
) -> str | None:
    attrs = {"property": property_} if property_ else {"name": name}
    tag = soup.find("meta", attrs=attrs)
    if isinstance(tag, Tag):
        content = tag.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    return None


def _extract_name(soup: BeautifulSoup) -> str | None:
    site_name = _meta_content(soup, property_="og:site_name")
    if site_name:
        return site_name
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return None


def _extract_description(soup: BeautifulSoup) -> str | None:
    og_description = _meta_content(soup, property_="og:description")
    return og_description or _meta_content(soup, name="description")


def _extract_contact(text: str) -> tuple[str | None, str | None]:
    phone_match = _PHONE_RE.search(text)
    email_match = _EMAIL_RE.search(text)
    phone = phone_match.group(0) if phone_match else None
    email = email_match.group(0) if email_match else None
    return phone, email


def _extract_social_links(soup: BeautifulSoup) -> dict[str, str]:
    links: dict[str, str] = {}
    for anchor in soup.find_all("a", href=True):
        if not isinstance(anchor, Tag):
            continue
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        for domain, key in _SOCIAL_DOMAINS.items():
            if domain in href and key not in links:
                links[key] = href
    return links


def _flatten_jsonld(candidate: dict[str, object], entries: list[dict[str, object]]) -> None:
    graph = candidate.get("@graph")
    if isinstance(graph, list):
        for item in graph:
            if isinstance(item, dict):
                _flatten_jsonld(item, entries)
        return
    entries.append(candidate)


def _iter_jsonld(soup: BeautifulSoup) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not isinstance(script, Tag) or not script.string:
            continue
        try:
            parsed = json.loads(script.string)
        except json.JSONDecodeError:
            continue
        candidates = parsed if isinstance(parsed, list) else [parsed]
        for candidate in candidates:
            if isinstance(candidate, dict):
                _flatten_jsonld(candidate, entries)
    return entries


def _jsonld_type_matches(entry: dict[str, object]) -> bool:
    raw_type = entry.get("@type")
    types = raw_type if isinstance(raw_type, list) else [raw_type]
    return any(isinstance(t, str) and t.lower() in _CHURCH_JSONLD_TYPES for t in types)


def _apply_jsonld(entry: dict[str, object], data: ExtractedData) -> None:
    name = entry.get("name")
    if isinstance(name, str) and not data.name:
        data.name = name

    telephone = entry.get("telephone")
    if isinstance(telephone, str) and not data.phone:
        data.phone = telephone

    email = entry.get("email")
    if isinstance(email, str) and not data.email:
        data.email = email

    address = entry.get("address")
    if isinstance(address, dict):
        data.street = data.street or _str_or_none(address.get("streetAddress"))
        data.city = data.city or _str_or_none(address.get("addressLocality"))
        data.region = data.region or _str_or_none(address.get("addressRegion"))
        data.postal_code = data.postal_code or _str_or_none(address.get("postalCode"))
        data.country = data.country or _str_or_none(address.get("addressCountry"))

    for spec in _as_list(entry.get("openingHoursSpecification")):
        if isinstance(spec, dict):
            data.service_times.extend(_service_times_from_spec(spec))


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _as_list(value: object) -> list[object]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _normalize_day_of_week(value: str) -> str:
    return value.rsplit("/", 1)[-1]


def _service_times_from_spec(spec: dict[str, object]) -> list[ExtractedServiceTime]:
    name = _str_or_none(spec.get("name"))
    opens = _str_or_none(spec.get("opens"))
    days = [d for d in _as_list(spec.get("dayOfWeek")) if isinstance(d, str)]

    if not days:
        return [ExtractedServiceTime(name=name, time=opens)]

    return [
        ExtractedServiceTime(name=name, day_of_week=_normalize_day_of_week(day), time=opens)
        for day in days
    ]


def extract(html: str) -> ExtractedData:
    """Extract best-effort church data from a page's HTML."""
    soup = BeautifulSoup(html, "html.parser")
    data = ExtractedData(
        name=_extract_name(soup),
        description=_extract_description(soup),
        social_links=_extract_social_links(soup),
    )

    for entry in _iter_jsonld(soup):
        if _jsonld_type_matches(entry):
            _apply_jsonld(entry, data)
    data.service_times = _dedupe_service_times(data.service_times)

    phone, email = _extract_contact(soup.get_text(separator=" "))
    data.phone = data.phone or phone
    data.email = data.email or email

    return data


def _dedupe_service_times(service_times: list[ExtractedServiceTime]) -> list[ExtractedServiceTime]:
    seen: set[tuple[str | None, str | None, str | None, str | None]] = set()
    deduped: list[ExtractedServiceTime] = []
    for service_time in service_times:
        key = (
            service_time.name,
            service_time.day_of_week,
            service_time.time,
            service_time.language,
        )
        if key not in seen:
            seen.add(key)
            deduped.append(service_time)
    return deduped
