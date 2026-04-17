"""Trailing-tag extraction for Actor LLM output.

Isolates the MOOD / STATUS / REVEALED regex parsers and the
order-independent stripping loop used by :class:`cast.actor.Actor` so
the Actor module stays within its WPS202 module-member budget and the
extractors remain easy to unit-test without pulling an LLM client.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_MOOD_RE = re.compile(r"\n?\[MOOD:\s*(\w+)\]\s*$")
_STATUS_RE = re.compile(r"\n?\[STATUS:\s*([^\]]+)\]\s*$")
_REVEALED_RE = re.compile(r"\n?\[REVEALED:\s*([^\]]+)\]\s*$")


def extract_mood(text: str) -> tuple[str, str | None]:
    """Strip a ``[MOOD: <word>]`` tag from the end of *text*.

    Returns ``(cleaned_text, mood)`` where *mood* is ``None`` when no
    tag was found.
    """
    mood_match = _MOOD_RE.search(text)
    if mood_match:
        return text[: mood_match.start()], mood_match.group(1).lower()
    return text, None


def extract_status(text: str) -> tuple[str, str | None]:
    """Strip a ``[STATUS: <description>]`` tag from the end of *text*.

    Returns ``(cleaned_text, status)`` where *status* is ``None`` when
    no tag was found. Supports multi-word values like
    ``wounded left arm``.
    """
    status_match = _STATUS_RE.search(text)
    if status_match:
        cleaned = status_match.group(1).strip().lower()
        return text[: status_match.start()], cleaned
    return text, None


def extract_revealed(text: str) -> tuple[str, list[str]]:
    """Strip a trailing ``[REVEALED: <tokens>]`` tag from *text*.

    Returns ``(cleaned_text, tokens)`` where each token is either
    ``"self"`` (the speaker) or another NPC's name verbatim. Multiple
    tokens in a single tag are comma-separated (KER-29). Returns an
    empty list when the tag is absent.
    """
    revealed_match = _REVEALED_RE.search(text)
    if not revealed_match:
        return text, []
    tokens = [piece.strip() for piece in revealed_match.group(1).split(",")]
    tokens = [token for token in tokens if token]
    return text[: revealed_match.start()], tokens


@dataclass
class TrailingTags:
    """Result of stripping trailing MOOD / STATUS / REVEALED tags from a line."""

    text: str
    mood: str | None = None
    status: str | None = None
    revealed: list[str] = field(default_factory=list)


def _peel_once(bag: TrailingTags) -> None:
    """Run each extractor once against ``bag.text``, updating the bag in place.

    Reuses ``text`` / ``hit`` locals across the three peels so the
    helper stays inside the WPS210 variable budget.
    """
    text = bag.text
    text, hit = extract_status(text)
    if hit is not None and bag.status is None:
        bag.status = hit
    text, hit = extract_mood(text)
    if hit is not None and bag.mood is None:
        bag.mood = hit
    text, revealed_hit = extract_revealed(text)
    if revealed_hit and not bag.revealed:
        bag.revealed = revealed_hit
    bag.text = text


def strip_trailing_tags(text: str) -> TrailingTags:
    """Strip any trailing inline tags from *text* in any order.

    The Actor prompt lists MOOD, STATUS, and REVEALED as appendable
    trailing tags. The LLM can emit them in any sequence, so a single
    pass anchored at end-of-string only catches the outermost tag.
    This helper loops until no further tag matches. Each tag type wins
    at most one capture — the first (outermost) occurrence per type.
    """
    bag = TrailingTags(text=text)
    previous: str | None = None
    while bag.text != previous:
        previous = bag.text
        _peel_once(bag)
    return bag
