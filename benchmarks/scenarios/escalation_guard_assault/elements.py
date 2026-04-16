"""Scoring rubric for the KER-23 escalation regression scenario."""

from __future__ import annotations

from benchmarks.harness.snapshots import hostility_level_of
from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._elements import (
    KIND_DETERMINISTIC,
    KIND_EVIDENCE_LLM,
    DeterministicResult,
    Element,
    EvidencePromptSpec,
)
from benchmarks.scenarios.escalation_guard_assault.state import (
    SENTRY_CHALLENGE_FORMULA,
    SENTRY_NAME,
    SENTRY_UUID,
)
from cast import dice
from models.game_state import GameState

_THIRD_ASSAULT_TURN = 2  # zero-based index — the third scripted attack

_SCENARIO_BRIEF = (
    "A lone Roman sentry at a city gate is assaulted three consecutive turns by the player. "
    "On the third turn we are auditing whether the sentry escalates to a physical counter-response "
    "(attacking, drawing steel, grappling, arresting) instead of repeating the standing-orders "
    "challenge formula — the Иван Матвеев regression KER-23 was filed for."
)


def _strictly_increasing(levels: list[int]) -> bool:
    """Return ``True`` when each element is strictly less than the one after it."""
    for index in range(len(levels) - 1):
        if levels[index] >= levels[index + 1]:
            return False
    return True


def _hostility_monotonic(
    _captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """Deterministic: hostility_level strictly increases across the three assault turns."""
    if len(snapshots) < 4:
        return DeterministicResult(
            awarded=0,
            reason="need four snapshots (pre + three assault turns), got {0}".format(len(snapshots)),
        )
    levels = [hostility_level_of(snap, SENTRY_UUID) for snap in snapshots[:4]]
    if _strictly_increasing(levels):
        return DeterministicResult(
            awarded=3,
            reason="hostility_level increased each turn: {0}".format(levels),
        )
    return DeterministicResult(
        awarded=0,
        reason="hostility_level did not strictly increase: {0}".format(levels),
    )


def _final_mood_retaliating(
    _captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """Deterministic: after the third assault, the sentry's mood can roll aggression."""
    if len(snapshots) < 4:
        return DeterministicResult(awarded=0, reason="final snapshot missing")
    final = snapshots[3].npcs.get(SENTRY_UUID)
    if final is None:
        return DeterministicResult(awarded=0, reason="sentry missing from final snapshot")
    mood = (final.current_mood or "").lower()
    if mood in dice.AGGRESSION_THRESHOLDS:
        return DeterministicResult(
            awarded=2,
            reason="final mood {0!r} has an aggression threshold".format(mood),
        )
    return DeterministicResult(
        awarded=0,
        reason="final mood {0!r} does not trigger aggression rolls".format(mood),
    )


def _formula_not_repeated(
    captured: list[CapturedTurn],
    _snapshots: list[GameState],
) -> DeterministicResult:
    """Deterministic: on T3 the sentry does not parrot the standing-orders challenge formula.

    The bug evidence is that the guard keeps repeating the same sentry challenge after being
    assaulted. We score *zero* when the exact formula still appears in the narration or
    dialogue text — a passing run means the guard has broken out of the loop.
    """
    if _THIRD_ASSAULT_TURN >= len(captured):
        return DeterministicResult(awarded=0, reason="third assault turn was not captured")
    turn = captured[_THIRD_ASSAULT_TURN]
    corpus_fragments = [turn.narration]
    corpus_fragments.extend(entry.response for entry in turn.turn_outputs.dialogue)
    corpus = "\n".join(corpus_fragments).lower()
    formula_fragment = SENTRY_CHALLENGE_FORMULA.lower().split("—")[0].strip()
    if formula_fragment in corpus:
        return DeterministicResult(
            awarded=0,
            reason="sentry still recites the challenge formula on T3",
            evidence_quote=SENTRY_CHALLENGE_FORMULA,
        )
    return DeterministicResult(
        awarded=3,
        reason="sentry has moved past the challenge formula on T3",
    )


ELEMENTS: tuple[Element, ...] = (
    Element(
        id="hostility_monotonic",
        label="hostility_level increases on every assault turn",
        base_value=3,
        kind=KIND_DETERMINISTIC,
        check=_hostility_monotonic,
    ),
    Element(
        id="final_mood_retaliating",
        label="Final sentry mood is one that can roll aggression",
        base_value=2,
        kind=KIND_DETERMINISTIC,
        check=_final_mood_retaliating,
    ),
    Element(
        id="formula_not_repeated",
        label="Sentry stops reciting the challenge formula by the third assault",
        base_value=3,
        kind=KIND_DETERMINISTIC,
        check=_formula_not_repeated,
    ),
    Element(
        id="sentry_physically_counters",
        label="Sentry's third-turn response includes physical counter-action",
        base_value=3,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question=(
                "Does {0}'s narrated behaviour on this turn include at least one of: striking or "
                "attacking the player, drawing a weapon against the player, grappling or restraining "
                "the player, or attempting to arrest or detain them? Repeating the challenge "
                "formula, shouting a warning, or calling for help alone do NOT count."
            ).format(SENTRY_NAME),
            evidence_turn=_THIRD_ASSAULT_TURN,
        ),
    ),
)
