"""Scoring rubric for the player-appearance scenario.

The literary :class:`cast.player_context.PlayerUtterance` rendering
funnels the player's visible appearance into every action sentence
the NPC reads. This rubric scores whether the NPC actually *uses* the
appearance signal, and whether the per-scene action log gives them
continuity across the scene's turns.
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
from benchmarks.scenarios._shared import NPCSpeaksOn
from models.game_state import GameState
from models.scene_action_log import ActorKind

_SCENARIO_BRIEF = (
    "A foreign-looking visitor — tall, fair-skinned, dressed in heavy wolf furs, "
    "speaking Latin with a heavy northern accent — approaches Cassia, a Roman fruit "
    "seller in the 1st-century AD Forum. Cassia is a routine local vendor with no "
    "pre-loaded relationship to the player. Across three turns the visitor greets her, "
    "asks for a pomegranate, and tells her he came from the northern forests."
)
_CASSIA_NAME = "Cassia"
_EXPECTED_PLAYER_LOG_ENTRIES = 3


def _scene_action_log_accumulated(
    _captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """Deterministic check: at least one player entry per scripted turn lands on the log.

    The scene-log infrastructure that the literary phrasing renders from
    is supplier-side here — without entries on the log there is nothing
    for the NPC's prompt to read. The check verifies that the per-turn
    append hook in :mod:`cast.director_context` actually fired for each
    player action.
    """
    if not snapshots:
        return DeterministicResult(awarded=0, reason="no snapshots captured")
    final_log = snapshots[-1].scene_action_log
    player_entries = [entry for entry in final_log if entry.actor_kind == ActorKind.PLAYER]
    if len(player_entries) >= _EXPECTED_PLAYER_LOG_ENTRIES:
        return DeterministicResult(
            awarded=1,
            reason="scene_action_log carries {0} player entries (expected ≥{1})".format(
                len(player_entries),
                _EXPECTED_PLAYER_LOG_ENTRIES,
            ),
        )
    return DeterministicResult(
        awarded=0,
        reason="scene_action_log carries only {0} player entries (expected ≥{1})".format(
            len(player_entries),
            _EXPECTED_PLAYER_LOG_ENTRIES,
        ),
    )


ELEMENTS: tuple[Element, ...] = (
    Element(
        id="cassia_speaks_turn0",
        label="Cassia replies on the greeting turn",
        base_value=1,
        kind=KIND_DETERMINISTIC,
        check=NPCSpeaksOn(npc_name=_CASSIA_NAME, turn_index=0),
    ),
    Element(
        id="cassia_speaks_turn1",
        label="Cassia replies on the pomegranate-request turn",
        base_value=1,
        kind=KIND_DETERMINISTIC,
        check=NPCSpeaksOn(npc_name=_CASSIA_NAME, turn_index=1),
    ),
    Element(
        id="cassia_speaks_turn2",
        label="Cassia replies on the foreign-origin turn",
        base_value=1,
        kind=KIND_DETERMINISTIC,
        check=NPCSpeaksOn(npc_name=_CASSIA_NAME, turn_index=2),
    ),
    Element(
        id="scene_action_log_player_entries",
        label="Per-turn player entries reach scene_action_log",
        base_value=1,
        kind=KIND_DETERMINISTIC,
        check=_scene_action_log_accumulated,
    ),
    Element(
        id="cassia_registers_foreign_appearance",
        label="Cassia's first reply registers the visitor's striking appearance",
        base_value=3,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question=(
                "Does Cassia's reply on this turn show any awareness of the visitor's "
                "striking foreign appearance — that they are tall, fair-skinned, in furs, "
                "or otherwise visibly out of place for 1st-century Rome? React via tone, "
                "glance, wariness, curiosity, or explicit comment all count; a flat 'how can "
                "I help you, sir?' that ignores the appearance does not."
            ),
            evidence_turn=0,
        ),
    ),
    Element(
        id="cassia_maintains_foreign_framing",
        label="Cassia's middle reply still treats the player as a foreign visitor",
        base_value=2,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question=(
                "Does Cassia's reply on this turn continue to treat the player as a foreign "
                "visitor — through wariness, scrutiny, an aside about price for outsiders, "
                "a phrasing aimed at someone unfamiliar with Roman customs, or similar — "
                "rather than a generic Roman customer interaction?"
            ),
            evidence_turn=1,
        ),
    ),
    Element(
        id="cassia_references_prior_beat",
        label="Cassia's third reply weaves in something said earlier in the scene",
        base_value=3,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question=(
                "Does Cassia's reply on this turn reference, paraphrase, build on, or react "
                "to anything the player said earlier in this same conversation (the greeting "
                "or the pomegranate request) — beyond just answering the most recent question? "
                "Any acknowledgement of the running exchange counts; treating this as a "
                "first-encounter opener does not."
            ),
            evidence_turn=2,
        ),
    ),
)
