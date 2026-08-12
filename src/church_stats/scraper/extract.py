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

_BOILERPLATE_TAGS = ("nav", "footer", "header", "script", "style")
_PAGE_TEXT_MAX_CHARS = 6000

_DAY_ALIASES: dict[str, str] = {
    "sun": "Sunday",
    "sunday": "Sunday",
    "sundays": "Sunday",
    "mon": "Monday",
    "monday": "Monday",
    "mondays": "Monday",
    "tue": "Tuesday",
    "tues": "Tuesday",
    "tuesday": "Tuesday",
    "tuesdays": "Tuesday",
    "wed": "Wednesday",
    "weds": "Wednesday",
    "wednesday": "Wednesday",
    "wednesdays": "Wednesday",
    "thu": "Thursday",
    "thur": "Thursday",
    "thurs": "Thursday",
    "thursday": "Thursday",
    "thursdays": "Thursday",
    "fri": "Friday",
    "friday": "Friday",
    "fridays": "Friday",
    "sat": "Saturday",
    "saturday": "Saturday",
    "saturdays": "Saturday",
}
_DAY_RE = re.compile(
    r"\b(" + "|".join(sorted(_DAY_ALIASES, key=len, reverse=True)) + r")\b", re.IGNORECASE
)
_TIME_TOKEN_RE = re.compile(
    r"\b(?P<hour>\d{1,2})(?::(?P<minute>[0-5]\d))?\s*(?P<meridiem>[ap]\.?m\.?)?", re.IGNORECASE
)
_LANGUAGE_RE = re.compile(r"\(([^)]+)\)")

_SERVICE_TIME_HEADING_RE = re.compile(
    r"service\s*times?|when\s+we\s+meet|worship\s*times?|meeting\s*times?"
    r"|weekend\s*services?|plan\s+your\s+visit",
    re.IGNORECASE,
)
_HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "strong", "b")
_MAX_SERVICE_TIME_CANDIDATES = 5

# A church's own text is trusted here (unlike scan_url's HTML, this is
# our own curated vocabulary), so exact, mostly-unambiguous denomination
# names/abbreviations only -- no bare generic words like "Baptist" or
# "Christian" that show up constantly in unrelated contexts.
_DENOMINATION_ALIASES: dict[str, str] = {
    "southern baptist": "Southern Baptist",
    "american baptist": "American Baptist",
    "national baptist": "National Baptist",
    "missionary baptist": "Missionary Baptist",
    "independent baptist": "Independent Baptist",
    "presbyterian church (u.s.a.)": "Presbyterian Church (U.S.A.)",
    "presbyterian church in america": "Presbyterian Church in America",
    "pcusa": "Presbyterian Church (U.S.A.)",
    "united methodist": "United Methodist",
    "african methodist episcopal": "African Methodist Episcopal",
    "evangelical lutheran church in america": "Evangelical Lutheran Church in America",
    "lutheran church–missouri synod": "Lutheran Church–Missouri Synod",
    "lutheran church-missouri synod": "Lutheran Church–Missouri Synod",
    "roman catholic": "Roman Catholic",
    "assemblies of god": "Assemblies of God",
    "church of the nazarene": "Church of the Nazarene",
    "seventh-day adventist": "Seventh-day Adventist",
    "united church of christ": "United Church of Christ",
    "christian church (disciples of christ)": "Christian Church (Disciples of Christ)",
    "orthodox church in america": "Orthodox Church in America",
    "greek orthodox": "Greek Orthodox",
    "episcopal": "Episcopal",
    "anglican": "Anglican",
    "pentecostal": "Pentecostal",
    "mennonite": "Mennonite",
    "quaker": "Quaker",
    "unitarian universalist": "Unitarian Universalist",
    "non-denominational": "Non-denominational",
    "nondenominational": "Non-denominational",
    "interdenominational": "Interdenominational",
}
_DENOMINATION_RE = re.compile(
    r"\b("
    + "|".join(re.escape(k) for k in sorted(_DENOMINATION_ALIASES, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)

_LEADER_TITLE_KEYWORDS = [
    "Senior Pastor",
    "Lead Pastor",
    "Founding Pastor",
    "Executive Pastor",
    "Associate Pastor",
    "Campus Pastor",
    "Youth Pastor",
    "Worship Pastor",
    "Teaching Pastor",
    "Children's Pastor",
    "Care Pastor",
    "Pastor",
    "Priest",
    "Rector",
    "Bishop",
    "Rabbi",
    "Imam",
    "Elder",
    "Deacon",
    "Reverend",
    "Minister",
    "Chaplain",
]
_TITLE_ALTERNATION = "|".join(
    re.escape(t) for t in sorted(_LEADER_TITLE_KEYWORDS, key=len, reverse=True)
)
_NAME_PATTERN = r"(?:[A-Z][a-zA-Z'’.-]*\s+){1,3}[A-Z][a-zA-Z'’.-]*"
_LEADER_NAME_TITLE_RE = re.compile(rf"\b({_NAME_PATTERN})\s*,\s*({_TITLE_ALTERNATION})\b")
_LEADER_TITLE_NAME_RE = re.compile(rf"\b({_TITLE_ALTERNATION})\s*[:\-–]\s*({_NAME_PATTERN})\b")
_LEADER_HEADING_RE = re.compile(
    r"our\s+staff|leadership|meet\s+the\s+team|our\s+pastors?|pastoral\s+staff"
    r"|our\s+team|our\s+clergy",
    re.IGNORECASE,
)
_MAX_LEADER_CANDIDATES = 5


@dataclass
class ExtractedServiceTime:
    name: str | None = None
    day_of_week: str | None = None
    time: str | None = None
    language: str | None = None
    raw_text: str | None = None


@dataclass
class _TimeToken:
    hour: int
    minute: int
    meridiem: str | None


@dataclass
class ExtractedLeader:
    name: str
    title: str | None = None


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
    denomination: str | None = None
    also_known_as: list[str] = field(default_factory=list)
    social_links: dict[str, str] = field(default_factory=dict)
    service_times: list[ExtractedServiceTime] = field(default_factory=list)
    leaders: list[ExtractedLeader] = field(default_factory=list)
    page_text: str = ""


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


def _extract_denomination(text: str) -> str | None:
    match = _DENOMINATION_RE.search(text)
    if not match:
        return None
    return _DENOMINATION_ALIASES[match.group(0).lower()]


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

    for alt_name in _as_list(entry.get("alternateName")):
        if isinstance(alt_name, str) and alt_name not in data.also_known_as:
            data.also_known_as.append(alt_name)

    for key in ("founder", "employee", "member"):
        for person in _as_list(entry.get(key)):
            leader = _leader_from_jsonld(person)
            if leader is not None:
                data.leaders.append(leader)


def _leader_from_jsonld(value: object) -> ExtractedLeader | None:
    if not isinstance(value, dict):
        return None
    name = _str_or_none(value.get("name"))
    if not name:
        return None
    return ExtractedLeader(name=name, title=_str_or_none(value.get("jobTitle")))


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


def _to_24h(hour: int, minute: int, meridiem: str) -> str:
    normalized = meridiem.lower().replace(".", "")
    if normalized.startswith("p") and hour != 12:
        hour += 12
    elif normalized.startswith("a") and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _resolve_times(segment: str) -> list[str]:
    tokens: list[_TimeToken] = []
    for match in _TIME_TOKEN_RE.finditer(segment):
        minute_group = match.group("minute")
        meridiem = match.group("meridiem")
        if minute_group is None and meridiem is None:
            continue  # too ambiguous to be a time (e.g. a bare number)
        hour = int(match.group("hour"))
        if not 1 <= hour <= 12:
            continue
        tokens.append(_TimeToken(hour=hour, minute=int(minute_group or "0"), meridiem=meridiem))

    # Forward-fill a missing meridiem from a later token in the same segment,
    # e.g. "9:00 & 11:00 AM" means both services are in the morning.
    last_meridiem: str | None = None
    for token in reversed(tokens):
        if token.meridiem is not None:
            last_meridiem = token.meridiem
        elif last_meridiem is not None:
            token.meridiem = last_meridiem

    return [_to_24h(token.hour, token.minute, token.meridiem) for token in tokens if token.meridiem]


def _parse_service_times_from_text(text: str) -> list[ExtractedServiceTime]:
    """Parse free text like "Sundays 9am & 11am" into structured service times.

    A day mention with no confidently-parseable time still produces an
    entry (day set, time left ``None``) so the original text survives in
    ``raw_text`` -- but only when *some* day in the same text resolved a
    real time. A block with no resolved times at all is too weak a signal
    (day names show up in plenty of unrelated page content) and is
    discarded entirely rather than adding noisy, timeless entries.
    """
    day_matches = list(_DAY_RE.finditer(text))
    candidates: list[ExtractedServiceTime] = []

    for index, day_match in enumerate(day_matches):
        segment_end = day_matches[index + 1].start() if index + 1 < len(day_matches) else len(text)
        segment = text[day_match.start() : segment_end].strip()
        day = _DAY_ALIASES[day_match.group(0).lower()]

        language_match = _LANGUAGE_RE.search(segment)
        language = language_match.group(1).strip() if language_match else None

        times = _resolve_times(segment)
        if not times:
            candidates.append(
                ExtractedServiceTime(day_of_week=day, language=language, raw_text=segment)
            )
            continue

        for time in times:
            candidates.append(
                ExtractedServiceTime(
                    day_of_week=day, time=time, language=language, raw_text=segment
                )
            )

    if not any(c.time for c in candidates):
        return []
    return candidates


def _find_service_time_candidates(soup: BeautifulSoup) -> list[str]:
    """Find text blocks likely to describe service times: a heading whose
    text matches common phrasing ("Service Times", "When We Meet", ...)
    plus its immediately following siblings."""
    candidates: list[str] = []
    seen: set[str] = set()

    for heading in soup.find_all(_HEADING_TAGS):
        if not isinstance(heading, Tag):
            continue
        heading_text = heading.get_text(" ", strip=True)
        if not _SERVICE_TIME_HEADING_RE.search(heading_text):
            continue

        parts = [heading_text]
        for sibling in heading.find_next_siblings(limit=3):
            if isinstance(sibling, Tag):
                sibling_text = sibling.get_text(" ", strip=True)
                if sibling_text:
                    parts.append(sibling_text)

        candidate = " ".join(parts).strip()
        if candidate and candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)

        if len(candidates) >= _MAX_SERVICE_TIME_CANDIDATES:
            break

    return candidates


def _find_leader_candidates(soup: BeautifulSoup) -> list[str]:
    """Find text blocks likely to list church leadership: a heading whose
    text matches common phrasing ("Our Staff", "Leadership", ...) plus its
    following siblings, joined with ", " so a name in its own element right
    before a title in the next one reads the same as "Name, Title" in a
    single line of text."""
    candidates: list[str] = []
    seen: set[str] = set()

    for heading in soup.find_all(_HEADING_TAGS):
        if not isinstance(heading, Tag):
            continue
        heading_text = heading.get_text(" ", strip=True)
        if not _LEADER_HEADING_RE.search(heading_text):
            continue

        parts = []
        for sibling in heading.find_next_siblings(limit=10):
            if isinstance(sibling, Tag):
                sibling_text = sibling.get_text(" ", strip=True)
                if sibling_text:
                    parts.append(sibling_text)

        candidate = ", ".join(parts).strip()
        if candidate and candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)

        if len(candidates) >= _MAX_LEADER_CANDIDATES:
            break

    return candidates


def _clean_leader(name: str, title: str) -> ExtractedLeader | None:
    name = name.strip().strip(",")
    title = title.strip()
    if not name or not title:
        return None
    return ExtractedLeader(name=name, title=title)


def _parse_leaders_from_text(text: str) -> list[ExtractedLeader]:
    """Parse "Name, Title" and "Title: Name" pairs, anchored on a curated
    title-keyword list so a comma between two capitalized words elsewhere
    on the page doesn't get misread as a leader."""
    leaders: list[ExtractedLeader] = []
    for match in _LEADER_NAME_TITLE_RE.finditer(text):
        leader = _clean_leader(match.group(1), match.group(2))
        if leader is not None:
            leaders.append(leader)
    for match in _LEADER_TITLE_NAME_RE.finditer(text):
        leader = _clean_leader(match.group(2), match.group(1))
        if leader is not None:
            leaders.append(leader)
    return leaders


def _dedupe_leaders(leaders: list[ExtractedLeader]) -> list[ExtractedLeader]:
    seen: set[tuple[str, str | None]] = set()
    deduped: list[ExtractedLeader] = []
    for leader in leaders:
        key = (leader.name, leader.title)
        if key not in seen:
            seen.add(key)
            deduped.append(leader)
    return deduped


def _extract_page_text(html: str) -> str:
    """Pull representative page text for downstream classification.

    Uses a separate parse of the same HTML so stripping boilerplate here
    doesn't affect the other extractors (social links, for one, often live
    in the footer we're removing).
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(_BOILERPLATE_TAGS):
        tag.decompose()

    parts = [part for part in (soup.title.string if soup.title else None,) if part]
    body_text = soup.get_text(separator=" ", strip=True)
    if body_text:
        parts.append(body_text)

    text = " ".join(part.strip() for part in parts if part.strip())
    return text[:_PAGE_TEXT_MAX_CHARS]


def extract(html: str) -> ExtractedData:
    """Extract best-effort church data from a page's HTML."""
    soup = BeautifulSoup(html, "html.parser")
    data = ExtractedData(
        name=_extract_name(soup),
        description=_extract_description(soup),
        social_links=_extract_social_links(soup),
        page_text=_extract_page_text(html),
    )

    for entry in _iter_jsonld(soup):
        if _jsonld_type_matches(entry):
            _apply_jsonld(entry, data)
    data.service_times = _dedupe_service_times(data.service_times)

    if not data.service_times:
        # JSON-LD is the trusted source (see module docstring); only fall
        # back to parsing free text near a "service times"-style heading
        # when the page didn't publish any structured hours.
        for candidate in _find_service_time_candidates(soup):
            data.service_times.extend(_parse_service_times_from_text(candidate))
        data.service_times = _dedupe_service_times(data.service_times)

    data.leaders = _dedupe_leaders(data.leaders)
    if not data.leaders:
        for candidate in _find_leader_candidates(soup):
            data.leaders.extend(_parse_leaders_from_text(candidate))
        data.leaders = _dedupe_leaders(data.leaders)

    full_text = soup.get_text(separator=" ")
    phone, email = _extract_contact(full_text)
    data.phone = data.phone or phone
    data.email = data.email or email
    data.denomination = _extract_denomination(full_text)

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
