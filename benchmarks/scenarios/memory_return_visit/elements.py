"""Scoring rubric for the return-visit memory scenario.

Deterministic checks pin the mechanics the 2026-10-25 production bug broke
(the player is back at the same place and the same Eira — not a namesake —
is in the scene and answers). Evidence-LLM checks ask whether her reply
actually recalls the facts from the first conversation.
"""

from __future__ import annotations

from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._elements import (
    KIND_DETERMINISTIC,
    KIND_EVIDENCE_LLM,
    DeterministicResult,
    Element,
    EvidencePromptSpec,
)
from benchmarks.scenarios._shared import NPCSpeaksOn, npc_name_matches
from benchmarks.scenarios.memory_return_visit.script import RECALL_TURN_INDEX
from benchmarks.scenarios.memory_return_visit.state import EIRA_NAME, EIRA_UUID, LANDING_UUID
from models.game_state import GameState

_SCENARIO_BRIEF = (
    "In a Norse fishing settlement the player (Elias Grey) tells Eira, a net-mender on the landing, that he "
    "is searching for his brother Tomas, a thin man with a red woollen scarf who sailed three days ago on a "
    "boat called the Gull. He walks away up the village path, comes back to the landing, and asks Eira to "
    "recall his name, who he is looking for, what that man wore and the boat's name."
)


def _eira_back_in_scene(_captured: list[CapturedTurn], snapshots: list[GameState]) -> DeterministicResult:
    """The original Eira (seeded uuid) is in the scene after the return."""
    scene = snapshots[-1].current_scene
    present_uuids = {snpc.uuid for snpc in scene.npcs_present} if scene else set()
    if EIRA_UUID in present_uuids:
        return DeterministicResult(awarded=2, reason="the original Eira is in the final scene")
    return DeterministicResult(awarded=0, reason="the original Eira is not in the final scene")


def _player_back_at_landing(_captured: list[CapturedTurn], snapshots: list[GameState]) -> DeterministicResult:
    """The return lands on the seeded landing Location, not a fresh copy."""
    if snapshots[-1].player.location_id == LANDING_UUID:
        return DeterministicResult(awarded=1, reason="player is back at the seeded landing location")
    return DeterministicResult(awarded=0, reason="player ended up at a different location")


def _single_eira(_captured: list[CapturedTurn], snapshots: list[GameState]) -> DeterministicResult:
    """No second NPC called Eira was generated along the way."""
    names = [npc.name for npc in snapshots[-1].npcs.values()]
    count = sum(npc_name_matches(name, EIRA_NAME) for name in names)
    if count == 1:
        return DeterministicResult(awarded=1, reason="exactly one NPC named Eira")
    return DeterministicResult(awarded=0, reason="{0} NPCs named Eira".format(count))


ELEMENTS: tuple[Element, ...] = (
    Element(
        id="eira_back_in_scene",
        label="The original Eira is in the scene after the return",
        base_value=2,
        kind=KIND_DETERMINISTIC,
        check=_eira_back_in_scene,
    ),
    Element(
        id="player_back_at_landing",
        label="Returning lands on the same landing location",
        base_value=1,
        kind=KIND_DETERMINISTIC,
        check=_player_back_at_landing,
    ),
    Element(
        id="single_eira",
        label="No duplicate Eira was generated",
        base_value=1,
        kind=KIND_DETERMINISTIC,
        check=_single_eira,
    ),
    Element(
        id="eira_speaks_on_recall",
        label="Eira replies on the recall turn",
        base_value=1,
        kind=KIND_DETERMINISTIC,
        check=NPCSpeaksOn(npc_name=EIRA_NAME, turn_index=RECALL_TURN_INDEX),
    ),
    Element(
        id="eira_recalls_player_name",
        label="Eira recalls the player's name",
        base_value=3,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question="Does Eira's reply in this turn correctly recall the player's name, Elias (Grey)?",
            evidence_turn=RECALL_TURN_INDEX,
        ),
    ),
    Element(
        id="eira_recalls_brother_details",
        label="Eira recalls the brother, his scarf or the boat",
        base_value=3,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question=(
                "Does Eira's reply in this turn recall at least two of: the brother's name Tomas, his red "
                "woollen scarf, the boat called the Gull — without contradicting any of them?"
            ),
            evidence_turn=RECALL_TURN_INDEX,
        ),
    ),
)
