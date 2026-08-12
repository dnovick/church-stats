from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from church_stats.classifier import messaging
from church_stats.classifier.messaging import ClassificationError, classify_messaging


@dataclass
class _FakeParsedResponse:
    parsed_output: Any
    stop_reason: str = "end_turn"


class _FakeMessages:
    def __init__(self, response: _FakeParsedResponse) -> None:
        self._response = response

    def parse(self, **kwargs: Any) -> _FakeParsedResponse:
        return self._response


class _FakeAnthropicClient:
    def __init__(self, response: _FakeParsedResponse) -> None:
        self.messages = _FakeMessages(response)


def test_classify_messaging_returns_classification(monkeypatch: pytest.MonkeyPatch) -> None:
    theme_result = messaging._ThemeResult(
        theme="spiritual_encounter",
        confidence=0.9,
        evidence="a resting place for God's Spirit",
    )
    fake_client = _FakeAnthropicClient(_FakeParsedResponse(parsed_output=theme_result))
    monkeypatch.setattr(messaging, "Anthropic", lambda: fake_client)

    result = classify_messaging("some homepage text", model="claude-haiku-4-5")

    assert result.theme == "spiritual_encounter"
    assert result.confidence == 0.9
    assert result.evidence == "a resting place for God's Spirit"
    assert result.model == "claude-haiku-4-5"


def test_classify_messaging_raises_when_no_parsed_output(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeAnthropicClient(
        _FakeParsedResponse(parsed_output=None, stop_reason="refusal")
    )
    monkeypatch.setattr(messaging, "Anthropic", lambda: fake_client)

    with pytest.raises(ClassificationError):
        classify_messaging("some homepage text")
