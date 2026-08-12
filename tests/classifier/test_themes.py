from __future__ import annotations

from typing import get_args

from church_stats.classifier.themes import THEME_DESCRIPTIONS
from church_stats.models import MessagingTheme


def test_every_theme_has_a_description() -> None:
    assert set(THEME_DESCRIPTIONS) == set(get_args(MessagingTheme))
