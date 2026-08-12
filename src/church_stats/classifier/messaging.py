"""Classify a church's outreach messaging into the controlled taxonomy via Claude."""

from __future__ import annotations

from datetime import datetime, timezone

from anthropic import Anthropic
from pydantic import BaseModel

from church_stats.classifier.themes import THEME_DESCRIPTIONS
from church_stats.models import MessagingClassification, MessagingTheme

DEFAULT_CLASSIFIER_MODEL = "claude-haiku-4-5"

_SYSTEM_PROMPT = (
    "You classify a church's website content by its primary outreach messaging theme "
    "-- the main way the church presents itself to attract visitors or new members. "
    "Choose exactly one theme from the closed set below, whichever best fits the "
    "page's overall tone and emphasis, and quote a short phrase from the page as "
    "evidence for your choice.\n\n"
    + "\n".join(f"- {theme}: {description}" for theme, description in THEME_DESCRIPTIONS.items())
)


class _ThemeResult(BaseModel):
    theme: MessagingTheme
    confidence: float
    evidence: str


class ClassificationError(RuntimeError):
    """Raised when Claude doesn't return a parseable classification (e.g. a refusal)."""


def classify_messaging(
    text: str, *, model: str = DEFAULT_CLASSIFIER_MODEL
) -> MessagingClassification:
    """Classify ``text`` (typically a church's homepage content) into a theme.

    Uses Claude structured outputs so the response is guaranteed to be one of
    the closed-set theme values. Credentials are resolved by the Anthropic
    SDK's normal mechanism (``ANTHROPIC_API_KEY`` env var or an ``ant auth
    login`` profile) -- nothing project-specific to configure.
    """
    client = Anthropic()
    response = client.messages.parse(
        model=model,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
        output_format=_ThemeResult,
    )
    result = response.parsed_output
    if result is None:
        raise ClassificationError(
            f"No classification returned (stop_reason={response.stop_reason!r})"
        )

    return MessagingClassification(
        theme=result.theme,
        confidence=result.confidence,
        evidence=result.evidence,
        model=model,
        classified_at=datetime.now(timezone.utc),
    )
