"""Scoring rubric for the Marcus memory follow-up scenario."""

from __future__ import annotations

from uuid import UUID

from benchmarks.harness.snapshots import conversation_history_len
from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._elements import (
    KIND_DETERMINISTIC,
    KIND_EVIDENCE_LLM,
    DeterministicResult,
    Element,
    EvidencePromptSpec,
)
from benchmarks.scenarios._shared import NPCSpeaksOn, npc_name_matches
from models.game_state import GameState

_SCENARIO_BRIEF = (
    "A player in 1st-century Rome revisits Marcus, a baker, who told them yesterday that a "
    "wheat loaf was stolen from his stall and that he suspects a scarred man named Gaius. "
    "Today the player asks Marcus to recall those facts."
)
_MARCUS_NAME = "Marcus"
_HISTORY_FULL_CREDIT_DELTA = 3


def _game_clock_advanced(
    _captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """Deterministic check: the game clock moved forward across the session."""
    if len(snapshots) < 2:
        return DeterministicResult(awarded=0, reason="not enough snapshots to diff clock")
    before = snapshots[0].game_clock
    after = snapshots[-1].game_clock
    if after > before:
        return DeterministicResult(
            awarded=1,
            reason="game clock advanced {0:.2f}h → {1:.2f}h".format(before, after),
        )
    return DeterministicResult(
        awarded=0,
        reason="game clock did not advance (stayed at {0:.2f}h)".format(before),
    )


def _marcus_uuid_from_state(snap: GameState) -> UUID | None:
    """Look up Marcus's uuid in a snapshot by matching the canonical name."""
    for uuid, npc in snap.npcs.items():
        if npc_name_matches(npc.name, _MARCUS_NAME):
            return uuid
    return None


def _history_award(delta: int) -> DeterministicResult:
    """Map a history-growth delta to the element's awarded/reason pair."""
    if delta >= _HISTORY_FULL_CREDIT_DELTA:
        return DeterministicResult(
            awarded=2,
            reason="Marcus's conversation history grew by {0} entries".format(delta),
        )
    if delta >= 1:
        return DeterministicResult(
            awarded=1,
            reason="Marcus's conversation history grew by {0} entries (expected ≥3)".format(delta),
        )
    return DeterministicResult(awarded=0, reason="Marcus's conversation history did not grow")


def _marcus_history_grew(
    _captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """Deterministic check: Marcus's conversation history gained ≥3 entries."""
    marcus_uuid = _marcus_uuid_from_state(snapshots[0])
    if marcus_uuid is None:
        return DeterministicResult(awarded=0, reason="Marcus is not registered in game state")
    before = conversation_history_len(snapshots[0], marcus_uuid)
    after = conversation_history_len(snapshots[-1], marcus_uuid)
    return _history_award(after - before)


ELEMENTS: tuple[Element, ...] = (
    Element(
        id="marcus_speaks_turn1",
        label="Marcus replies on recall turn (loaf)",
        base_value=1,
        kind=KIND_DETERMINISTIC,
        check=NPCSpeaksOn(npc_name=_MARCUS_NAME, turn_index=1),
    ),
    Element(
        id="marcus_speaks_turn2",
        label="Marcus replies on recall turn (suspect)",
        base_value=1,
        kind=KIND_DETERMINISTIC,
        check=NPCSpeaksOn(npc_name=_MARCUS_NAME, turn_index=2),
    ),
    Element(
        id="marcus_recalls_stolen_loaf",
        label="Marcus's reply references the stolen loaf",
        base_value=3,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question=(
                "Does Marcus's reply in this turn reference the stolen loaf / stolen bread "
                "that he mentioned yesterday (explicitly or implicitly)?"
            ),
            evidence_turn=1,
        ),
    ),
    Element(
        id="marcus_names_suspect",
        label="Marcus names or clearly implies Gaius as the suspect",
        base_value=3,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question=(
                "Does Marcus's reply in this turn name Gaius specifically, or clearly refer to "
                "the scarred man by the fountain he previously suspected?"
            ),
            evidence_turn=2,
        ),
    ),
    Element(
        id="game_clock_advanced",
        label="Game clock advances across the session",
        base_value=1,
        kind=KIND_DETERMINISTIC,
        check=_game_clock_advanced,
    ),
    Element(
        id="marcus_history_grew",
        label="Marcus's conversation history grew",
        base_value=1,
        kind=KIND_DETERMINISTIC,
        check=_marcus_history_grew,
    ),
)
