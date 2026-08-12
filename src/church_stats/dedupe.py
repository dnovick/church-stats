"""Flag likely-duplicate church records for user-confirmed merging.

This only detects candidates -- it never merges anything on its own. See
``church-stats duplicates`` and ``church-stats merge`` in ``cli.py``, and
``ChurchRepository.merge`` for the actual merge logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from itertools import combinations

from church_stats.models import ChurchRecord

_NAME_SIMILARITY_THRESHOLD = 0.6
_WEAK_NAME_SIMILARITY_THRESHOLD = 0.4


@dataclass
class DuplicateCandidate:
    first_id: str
    second_id: str
    reasons: list[str] = field(default_factory=list)


def _normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    return digits or None


def _name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()


def _same_normalized(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return a.strip().lower() == b.strip().lower()


def _compare(a: ChurchRecord, b: ChurchRecord) -> DuplicateCandidate | None:
    reasons: list[str] = []
    name_ratio = _name_similarity(a.name, b.name)

    if name_ratio >= _NAME_SIMILARITY_THRESHOLD:
        reasons.append(f"similar name ({name_ratio:.0%})")

    a_phone, b_phone = _normalize_phone(a.phone), _normalize_phone(b.phone)
    if a_phone is not None and a_phone == b_phone:
        reasons.append("matching phone number")

    same_location = _same_normalized(a.address.city, b.address.city) and _same_normalized(
        a.address.region, b.address.region
    )
    if same_location and name_ratio >= _WEAK_NAME_SIMILARITY_THRESHOLD:
        reasons.append(f"same city/region + similar name ({name_ratio:.0%})")

    if not reasons:
        return None
    return DuplicateCandidate(first_id=a.id, second_id=b.id, reasons=reasons)


def find_duplicates(records: list[ChurchRecord]) -> list[DuplicateCandidate]:
    """Pairwise-compare stored records and flag likely duplicates for review."""
    candidates = []
    for a, b in combinations(records, 2):
        candidate = _compare(a, b)
        if candidate is not None:
            candidates.append(candidate)
    return candidates
