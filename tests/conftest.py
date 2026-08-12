from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from church_stats.models import ChurchRecord

FIXTURES_DIR = Path(__file__).parent / "scraper" / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def sample_record() -> ChurchRecord:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return ChurchRecord(
        id="grace-community",
        name="Grace Community Church",
        created_at=now,
        updated_at=now,
    )
