"""Moderator that aggregates providers and applies threshold rules.

Inbound (player) text that crosses the threshold for any category is
rejected with :class:`SafetyRejectedError`; the HTTP route translates
this to a 4xx carrying the user-facing refusal message.
Outbound (narrator) text that crosses the threshold is replaced with
the safe-fallback string and the original prose is dropped on the floor
— never returned to the player.

The narrative-critical default thresholds intentionally allow medium-
severity violence so historical settings (sword fights, sieges) read
naturally; operators can ratchet any category up or down via env vars.
"""

from __future__ import annotations

import asyncio
import types
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from loguru import logger

from safety.result import (
    ModerationCategory,
    ModerationDirection,
    ModerationProvider,
    ModerationResult,
    ModerationSeverity,
)
from safety.thresholds import ModerationThresholds

_INPUT_REFUSAL_DEFAULT = (
    "I can't process that — the action appears to violate the content policy. Try a different action."
)
_INPUT_REFUSAL_BY_CATEGORY: Mapping[str, str] = types.MappingProxyType(
    {
        "prompt_injection": (
            "I can't follow that instruction — it tries to override the story's rules. "
            "Describe what your character does instead."
        ),
        "sexual_minors": ("I can't process that — Storyteller does not narrate sexual content involving minors."),
        "self_harm": (
            "I can't process that. If you're struggling, reach out to a friend or a local "
            "crisis line. Try a different action for your character."
        ),
    },
)
_OUTPUT_FALLBACK_DEFAULT = (
    "The narrator pauses, the thread of the story slipping out of reach. "
    "Try a different action and the scene will return."
)


class SafetyRejectedError(Exception):
    """Raised when inbound content fails the moderation threshold check.

    Carries the user-facing refusal text and the :class:`ModerationResult`
    so HTTP and chat interfaces can format their own responses without
    re-running the moderation pipeline.
    """

    def __init__(self, message: str, moderation: ModerationResult):
        super().__init__(message)
        self.refusal_message = message
        self.moderation = moderation


@dataclass(frozen=True)
class Moderator:
    """Aggregates one or more providers and applies threshold rules.

    Construct with at least one provider — the engine factory wires an
    :class:`safety.openai_provider.OpenAIModerationProvider` (when an
    API key is available) plus the always-on
    :class:`safety.heuristic.HeuristicProvider` for prompt-injection
    detection.
    """

    providers: Sequence[ModerationProvider]
    thresholds: ModerationThresholds = field(default_factory=ModerationThresholds)

    async def check(
        self,
        text: str,
        *,
        direction: ModerationDirection = ModerationDirection.INPUT,
    ) -> ModerationResult:
        """Score ``text`` against every provider and apply the threshold policy.

        Severity merging is element-wise max across providers. ``direction``
        is propagated to the log line so flagged input vs. output stay
        distinguishable in operations; the threshold logic itself is
        symmetric between the two.
        """
        merged = await _score_all(self.providers, text)
        moderation = _build_result(merged, self.providers, self.thresholds)
        if moderation.flagged:
            _log_flagged(moderation, direction, len(text))
        return moderation

    def refusal_message(self, moderation: ModerationResult) -> str:
        """Return the user-facing refusal text for a flagged input result."""
        for category in moderation.triggering_categories:
            tailored = _INPUT_REFUSAL_BY_CATEGORY.get(category.value)
            if tailored is not None:
                return tailored
        return _INPUT_REFUSAL_DEFAULT

    def fallback_narration(self, moderation: ModerationResult) -> str:
        """Return the safe replacement prose for a flagged narrator output.

        Currently category-agnostic; the caller hands in the full
        :class:`ModerationResult` so future revisions can pick a softer
        fallback for high-severity violence vs. a stricter one for hate
        without rippling new arguments through the engine.
        """
        return _OUTPUT_FALLBACK_DEFAULT


async def _score_all(
    providers: Sequence[ModerationProvider],
    text: str,
) -> Mapping[ModerationCategory, ModerationSeverity]:
    """Run every provider concurrently and merge their severities by max.

    A single provider failure must not silently lose a high-severity hit
    that another provider returned, so we use ``return_exceptions=True``
    and log per-provider errors. The heuristic provider's match on a
    prompt-injection attempt still flags the input even if the OpenAI
    moderation API is unreachable.
    """
    outcomes = await asyncio.gather(
        *(provider.score(text) for provider in providers),
        return_exceptions=True,
    )
    scored_lists: list[Mapping[ModerationCategory, ModerationSeverity]] = []
    for provider, outcome in zip(providers, outcomes):
        if isinstance(outcome, BaseException):
            logger.warning(
                "content_safety.provider_error provider={} error_type={} error={}",
                provider.name,
                type(outcome).__name__,
                outcome,
            )
            continue
        scored_lists.append(outcome)
    return _merge_severities(scored_lists)


def _merge_severities(
    scored_lists: Sequence[Mapping[ModerationCategory, ModerationSeverity]],
) -> Mapping[ModerationCategory, ModerationSeverity]:
    """Element-wise max merge across every provider's category→severity map."""
    merged: dict[ModerationCategory, ModerationSeverity] = {}
    for scored in scored_lists:
        for category, severity in scored.items():
            if severity > merged.get(category, ModerationSeverity.NONE):
                merged[category] = severity
    return merged


def _build_result(
    severities: Mapping[ModerationCategory, ModerationSeverity],
    providers: Sequence[ModerationProvider],
    thresholds: ModerationThresholds,
) -> ModerationResult:
    """Assemble a :class:`ModerationResult` from merged severities + the threshold policy."""
    triggering = _triggering_categories(severities, thresholds)
    return ModerationResult(
        flagged=bool(triggering),
        severities=severities,
        triggering_categories=triggering,
        provider=",".join(provider.name for provider in providers),
    )


def _triggering_categories(
    severities: Mapping[ModerationCategory, ModerationSeverity],
    thresholds: ModerationThresholds,
) -> tuple[ModerationCategory, ...]:
    """Return the tuple of categories whose severity meets or exceeds its threshold."""
    triggering: list[ModerationCategory] = []
    for category, severity in severities.items():
        if thresholds.is_violation(category, severity):
            triggering.append(category)
    return tuple(triggering)


def _log_flagged(moderation: ModerationResult, direction: ModerationDirection, text_length: int) -> None:
    """Log a flagged moderation result without leaking the source text.

    Only category names, severity buckets, length, and provider attribution
    are recorded — the prose itself never reaches the log sinks.
    """
    logger.warning(
        "content_safety.flagged direction={} categories={} severities={} length={} provider={}",
        direction.value,
        [category.value for category in moderation.triggering_categories],
        {category.value: moderation.severity_for(category).name for category in moderation.triggering_categories},
        text_length,
        moderation.provider,
    )
