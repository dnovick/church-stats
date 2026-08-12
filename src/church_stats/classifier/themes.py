"""The controlled taxonomy of church outreach-messaging themes.

This is a first draft (see the "Schema change" issue template for how to
propose additions/edits) — treat it as something to refine once it's been
run against a batch of real churches, not a fixed vocabulary.
"""

from __future__ import annotations

from church_stats.models import MessagingTheme

THEME_DESCRIPTIONS: dict[MessagingTheme, str] = {
    "community_belonging": (
        'Emphasizes relationships, "family," belonging, and connection with others.'
    ),
    "spiritual_encounter": "Emphasizes experiencing God's presence, worship, or the Holy Spirit.",
    "biblical_teaching": "Emphasizes sound doctrine and in-depth Bible teaching.",
    "practical_relevance": "Emphasizes real-life application and relevant, practical messages.",
    "outreach_service": "Emphasizes serving others, mission work, or social justice.",
    "traditional_reverence": (
        "Emphasizes liturgy, tradition, and a sacred/reverent worship experience."
    ),
    "casual_accessible": 'Emphasizes a casual, no-pressure, "come as you are" atmosphere.',
    "family_kids": "Emphasizes family ministry and children's programs.",
    "personal_growth": "Emphasizes discipleship, spiritual growth, and becoming your best self.",
    "other_unclear": "The page does not clearly signal a primary messaging theme.",
}
