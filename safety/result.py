"""Shared result types for the content-safety pipeline.

These types are consumed by every provider and by the moderator itself.
Keeping them in a leaf module avoids the import cycle that would
otherwise form between :mod:`safety.moderator` and the providers in
:mod:`safety.heuristic` / :mod:`safety.openai_provider`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class ModerationSeverity(Enum):
    """Coarse severity buckets that each provider must map its scores to.

    Ordering is meaningful: ``HIGH > MEDIUM > LOW > NONE``. Comparison
    operators are wired below so that ``severity >= threshold`` works.
    """

    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, ModerationSeverity):
            return NotImplemented
        return self.value >= other.value

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, ModerationSeverity):
            return NotImplemented
        return self.value > other.value

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ModerationSeverity):
            return NotImplemented
        return self.value < other.value

    def __le__(self, other: object) -> bool:
        if not isinstance(other, ModerationSeverity):
            return NotImplemented
        return self.value <= other.value


class ModerationCategory(Enum):
    """Categories the moderator can flag.

    ``PROMPT_INJECTION`` is carried by the heuristic provider — the OpenAI
    moderation endpoint does not surface a comparable signal.
    """

    VIOLENCE = "violence"
    SEXUAL = "sexual"
    SEXUAL_MINORS = "sexual_minors"
    HARASSMENT = "harassment"
    HATE = "hate"
    SELF_HARM = "self_harm"
    ILLICIT = "illicit"
    PROMPT_INJECTION = "prompt_injection"


class ModerationDirection(Enum):
    """Whether the moderator is checking player text or narrator text."""

    INPUT = "input"
    OUTPUT = "output"


@dataclass(frozen=True)
class ModerationResult:
    """The merged outcome of one or more :class:`ModerationProvider` calls.

    ``severities`` is a category→severity map covering every category that
    was scored (categories not present default to ``NONE`` on lookup).
    ``triggering_categories`` lists the categories whose severity met or
    exceeded the configured threshold; empty when ``flagged`` is False.
    """

    flagged: bool
    severities: Mapping[ModerationCategory, ModerationSeverity]
    triggering_categories: tuple[ModerationCategory, ...] = ()
    provider: str = ""

    def severity_for(self, category: ModerationCategory) -> ModerationSeverity:
        """Return the recorded severity for ``category`` (``NONE`` if absent)."""
        return self.severities.get(category, ModerationSeverity.NONE)


class ModerationProvider(Protocol):
    """Backend that scores a piece of text and returns severities."""

    name: str

    async def score(self, text: str) -> Mapping[ModerationCategory, ModerationSeverity]:
        """Return a category→severity map for ``text``.

        Categories the provider does not score should be omitted (callers
        treat absent entries as :attr:`ModerationSeverity.NONE`).
        """
        ...
