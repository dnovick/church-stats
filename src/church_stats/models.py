"""Pydantic schema for church records.

The schema is intentionally flexible: ``ChurchRecord`` allows extra fields so
scrapers and manual edits can stash not-yet-modeled data without validation
errors. Well-known fields get promoted into the model deliberately over time
(see CLAUDE.md). ``schema_version`` exists so ``storage`` can migrate older
records if the model shape changes in a breaking way.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

CURRENT_SCHEMA_VERSION = 1


class SourceRecord(BaseModel):
    """Provenance for a piece of data: where it came from and how."""

    url: HttpUrl
    fetched_at: datetime
    method: Literal["scraped", "manual", "imported"]


class Address(BaseModel):
    street: str | None = None
    city: str | None = None
    region: str | None = None
    postal_code: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class ServiceTime(BaseModel):
    name: str | None = None
    day_of_week: str | None = None
    time: str | None = None
    language: str | None = None
    raw_text: str | None = None


class Leader(BaseModel):
    name: str
    title: str | None = None


class SocialLinks(BaseModel):
    facebook: HttpUrl | None = None
    instagram: HttpUrl | None = None
    youtube: HttpUrl | None = None
    x: HttpUrl | None = None
    other: dict[str, HttpUrl] = Field(default_factory=dict)


MessagingTheme = Literal[
    "community_belonging",
    "spiritual_encounter",
    "biblical_teaching",
    "practical_relevance",
    "outreach_service",
    "traditional_reverence",
    "casual_accessible",
    "family_kids",
    "personal_growth",
    "other_unclear",
]


class MessagingClassification(BaseModel):
    """A church's primary outreach message, classified from scraped page text."""

    theme: MessagingTheme
    confidence: float
    evidence: str
    model: str
    classified_at: datetime


class ChurchRecord(BaseModel):
    """A single church's data. Extra fields are allowed for schema flexibility."""

    model_config = ConfigDict(extra="allow")

    schema_version: int = CURRENT_SCHEMA_VERSION
    id: str
    name: str
    also_known_as: list[str] = Field(default_factory=list)
    denomination: str | None = None
    website: HttpUrl | None = None
    description: str | None = None
    address: Address = Field(default_factory=Address)
    phone: str | None = None
    email: str | None = None
    service_times: list[ServiceTime] = Field(default_factory=list)
    leaders: list[Leader] = Field(default_factory=list)
    social_links: SocialLinks = Field(default_factory=SocialLinks)
    tags: list[str] = Field(default_factory=list)
    sources: list[SourceRecord] = Field(default_factory=list)
    messaging: MessagingClassification | None = None
    created_at: datetime
    updated_at: datetime
    notes: str | None = None
