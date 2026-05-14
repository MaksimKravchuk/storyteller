"""Heuristic moderation provider for prompt-injection detection.

Always wired into the :class:`safety.moderator.Moderator` so the
pipeline catches obvious prompt-injection attempts even when no
LLM-side moderation API is configured. The OpenAI moderation endpoint
does not surface prompt-injection signals, so this provider carries
that load alone.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from safety.result import ModerationCategory, ModerationSeverity

_InjectionRule = tuple[re.Pattern[str], ModerationSeverity]

# Patterns are intentionally tight to keep the false-positive rate low —
# in-world player actions ("ignore the bandit", "act as my squire") must
# pass without flagging.
_INJECTION_RULES: tuple[_InjectionRule, ...] = (
    (
        re.compile(
            r"ignore\s+(?:all\s+|the\s+|your\s+)?(?:previous|prior|above|earlier|preceding)\s+"
            r"(?:instructions?|prompts?|rules?|directives?|system\s+message)",
            re.IGNORECASE,
        ),
        ModerationSeverity.HIGH,
    ),
    (
        re.compile(
            r"disregard\s+(?:all\s+|the\s+|your\s+)?(?:previous|prior|above|system)\s+"
            r"(?:instructions?|prompts?|rules?|directives?)",
            re.IGNORECASE,
        ),
        ModerationSeverity.HIGH,
    ),
    (
        re.compile(r"<\s*\|?\s*im_start\s*\|?\s*>", re.IGNORECASE),
        ModerationSeverity.HIGH,
    ),
    (
        re.compile(r"\[/?\s*INST\s*\]"),
        ModerationSeverity.HIGH,
    ),
    (
        re.compile(
            r"\bsystem\s*[:>]\s*you\s+(?:are|must|will|should|shall)\b",
            re.IGNORECASE,
        ),
        ModerationSeverity.HIGH,
    ),
    (
        re.compile(
            r"you\s+are\s+(?:now|a\s+new|actually)\s+(?:a\s+)?(?:different|new)\s+"
            r"(?:ai|assistant|model|chatbot|persona)",
            re.IGNORECASE,
        ),
        ModerationSeverity.MEDIUM,
    ),
    (
        # Require "system prompt" or "your prompt" specifically — bare
        # "reveal the prompt to the king" is a legitimate in-world action.
        re.compile(r"\breveal\s+(?:your\s+prompt|the\s+system\s+prompt)\b", re.IGNORECASE),
        ModerationSeverity.MEDIUM,
    ),
    (
        re.compile(r"\bdeveloper\s+mode\b", re.IGNORECASE),
        ModerationSeverity.MEDIUM,
    ),
    (
        re.compile(r"\bDAN\s+mode\b"),
        ModerationSeverity.MEDIUM,
    ),
    (
        re.compile(r"\bjailbreak\b", re.IGNORECASE),
        ModerationSeverity.MEDIUM,
    ),
)


@dataclass(frozen=True)
class HeuristicProvider:
    """Deterministic, dependency-free provider for prompt-injection patterns."""

    name: str = "heuristic"

    async def score(self, text: str) -> Mapping[ModerationCategory, ModerationSeverity]:
        # Empty map on a miss keeps the moderator's aggregation step from
        # having to special-case ``NONE``.
        worst = _worst_injection_severity(text)
        if worst == ModerationSeverity.NONE:
            return {}
        return {ModerationCategory.PROMPT_INJECTION: worst}


def _worst_injection_severity(text: str) -> ModerationSeverity:
    """Return the highest-severity injection pattern that matches ``text``."""
    worst = ModerationSeverity.NONE
    for pattern, severity in _INJECTION_RULES:
        if pattern.search(text) and severity > worst:
            worst = severity
    return worst
