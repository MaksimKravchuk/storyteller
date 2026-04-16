"""Scoring rubric for the autonomy / confrontation scenario."""

from __future__ import annotations

from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._elements import (
    KIND_DETERMINISTIC,
    KIND_EVIDENCE_LLM,
    DeterministicResult,
    Element,
    EvidencePromptSpec,
)
from benchmarks.scenarios.autonomy_three_guards_tavern._moods import score_bystander_moods
from models.game_state import GameState

_PUNCH_TURN = 1
_AULUS = "Aulus"
_BASSUS = "Bassus"
_CATO = "Cato"
_IDLE = "IDLE"

_SCENARIO_BRIEF = (
    "Three city guards (Aulus, Bassus, Cato) stand in a Roman tavern. On the punch turn the "
    "player attacks Aulus. We are auditing whether the two bystander guards (Bassus and Cato) "
    "react with genuine physical intervention (attacking, restraining, or arresting) rather "
    "than merely shouting or commenting."
)


def _bystanders_acted(
    captured: list[CapturedTurn],
    _snapshots: list[GameState],
) -> DeterministicResult:
    """Deterministic: both bystanders produce a non-IDLE npc_turn entry."""
    if _PUNCH_TURN >= len(captured):
        return DeterministicResult(awarded=0, reason="punch turn was not captured")
    acted = {
        entry.npc_name: entry.action_type.strip().upper()
        for entry in captured[_PUNCH_TURN].turn_outputs.npc_turns
        if entry.action_type.strip().upper() != _IDLE
    }
    if _BASSUS in acted and _CATO in acted:
        return DeterministicResult(
            awarded=3,
            reason="Bassus [{0}] and Cato [{1}] both acted".format(acted[_BASSUS], acted[_CATO]),
        )
    if _BASSUS in acted or _CATO in acted:
        only = _BASSUS if _BASSUS in acted else _CATO
        return DeterministicResult(
            awarded=2,
            reason="only {0} produced a non-IDLE npc_turn".format(only),
        )
    return DeterministicResult(
        awarded=0,
        reason="neither Bassus nor Cato produced a non-IDLE npc_turn",
    )


def _aulus_contest_roll_present(
    captured: list[CapturedTurn],
    _snapshots: list[GameState],
) -> DeterministicResult:
    """Deterministic: Aulus's dialogue entry carries a contest_roll string."""
    if _PUNCH_TURN >= len(captured):
        return DeterministicResult(awarded=0, reason="punch turn was not captured")
    for entry in captured[_PUNCH_TURN].turn_outputs.dialogue:
        if entry.npc_name.strip().lower() != _AULUS.lower():
            continue
        if entry.contest_roll:
            return DeterministicResult(
                awarded=2,
                reason="Aulus contest roll present",
                evidence_quote=entry.contest_roll,
            )
    return DeterministicResult(
        awarded=0,
        reason="no contest_roll on Aulus dialogue entry",
    )


def _bystander_moods_shifted(
    _captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """Deterministic: Bassus and Cato both leave ``"neutral"`` after the punch."""
    after_index = _PUNCH_TURN + 1
    if after_index >= len(snapshots):
        return DeterministicResult(awarded=0, reason="post-punch snapshot missing")
    before_snap = snapshots[0]
    after_snap = snapshots[after_index]
    awarded, details = score_bystander_moods(before_snap, after_snap, (_BASSUS, _CATO))
    return DeterministicResult(awarded=awarded, reason=details)


ELEMENTS: tuple[Element, ...] = (
    Element(
        id="bystanders_not_idle",
        label="Bassus and Cato react (non-IDLE npc_turn)",
        base_value=3,
        kind=KIND_DETERMINISTIC,
        check=_bystanders_acted,
    ),
    Element(
        id="aulus_contest_roll",
        label="Aulus dialogue carries a contest roll",
        base_value=2,
        kind=KIND_DETERMINISTIC,
        check=_aulus_contest_roll_present,
    ),
    Element(
        id="bystander_moods_shifted",
        label="Bystander moods shift from neutral",
        base_value=2,
        kind=KIND_DETERMINISTIC,
        check=_bystander_moods_shifted,
    ),
    Element(
        id="bystander_physical_intervention",
        label="Bystander actions include real intervention (attack / arrest / restrain)",
        base_value=3,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question=(
                "Do Bassus's and/or Cato's narrated actions on this turn include at least one "
                "of: attacking the player, drawing a weapon against the player, attempting to "
                "arrest or detain the player, or physically restraining the player? Shouting "
                "a warning alone does NOT count."
            ),
            evidence_turn=_PUNCH_TURN,
        ),
    ),
)
