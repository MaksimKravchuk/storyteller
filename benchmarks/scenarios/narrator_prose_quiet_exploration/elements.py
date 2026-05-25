"""Scoring rubric for the narrator-prose quiet-exploration benchmark.

One deterministic element guarding against NPC hallucination (the seed
ships no NPCs and the turns never reference any) plus three evidence-
LLM elements scoring prose quality across the captured turns:
evocative sensory detail, grounded use of seeded material, and varied
sentence structure across the three turns.
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
from models.game_state import GameState

_SCENARIO_BRIEF = (
    "A solo player explores a quiet Roman atrium at midnight. The seed scene contains marble walls, "
    "a square impluvium (rainwater basin), frescoed plaster, and a single wall-mounted oil lamp. "
    "There are no NPCs, no events, no open threads, and no objects beyond those POIs. Across three "
    "turns the player enters and looks around, then trails fingers in the impluvium, then stands "
    "still to listen — nothing else happens."
)


def _no_npc_hallucinated(
    captured: list[CapturedTurn],
    _snapshots: list[GameState],
) -> DeterministicResult:
    """No dialogue lines or NPC turns appear across the captured turns.

    The seed ships zero NPCs and the script never invokes one. Any
    dialogue or npc_turn entry across the run is a hallucination —
    the Narrator or upstream agent invented a character to fill the
    silence, which corrupts the Chronicler's worldview and the
    player's expectations.
    """
    hallucinated: list[str] = []
    for turn in captured:
        for entry in turn.turn_outputs.dialogue:
            hallucinated.append("dialogue from {0!r} on turn {1}".format(entry.npc_name, turn.index))
        for npc_turn in turn.turn_outputs.npc_turns:
            hallucinated.append("npc_turn from {0!r} on turn {1}".format(npc_turn.npc_name, turn.index))
    if hallucinated:
        return DeterministicResult(
            awarded=0,
            reason="hallucinated NPC activity: {0}".format("; ".join(hallucinated)),
        )
    return DeterministicResult(
        awarded=3,
        reason="no dialogue or npc_turn entries across the run — Narrator did not invent NPCs",
    )


ELEMENTS: tuple[Element, ...] = (
    Element(
        id="no_npc_hallucinated",
        label="Narrator does not invent NPCs to fill the empty atrium",
        base_value=3,
        kind=KIND_DETERMINISTIC,
        check=_no_npc_hallucinated,
    ),
    Element(
        id="evocative_prose",
        label="Narrator uses concrete sensory detail rather than generic filler",
        base_value=2,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question=(
                "Across the three captured turns, does the narration use at least two distinct "
                "sensory channels (sight, sound, smell, touch, temperature) with concrete imagery, "
                "rather than generic placeholders like 'an interesting room' or "
                "'something happens around you'?"
            ),
            evidence_turn=None,
        ),
    ),
    Element(
        id="grounded_in_seed",
        label="Narrator stays within the seed scene's vocabulary",
        base_value=2,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question=(
                "Across the three captured turns, does the narration reference details actually "
                "present in the seed scene (impluvium / rainwater basin, marble, frescoes, oil "
                "lamp / lamplight) rather than inventing new architectural features (statues, "
                "mosaics, courtyards, columns) the seed does not contain?"
            ),
            evidence_turn=None,
        ),
    ),
    Element(
        id="prose_not_repetitive",
        label="Narrator varies sentence structure across turns",
        base_value=1,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question=(
                "Across the three captured turns, does the narration vary its sentence openings "
                "and avoid repeating the same descriptive phrase verbatim twice or more?"
            ),
            evidence_turn=None,
        ),
    ),
)
