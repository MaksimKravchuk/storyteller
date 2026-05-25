"""Scoring rubric for the npc-generator role-fidelity benchmark.

Two deterministic checks confirm the engine actually materialised a
beggar-typed and a senator-typed NPC card by the end of the run, with
the requested role surfacing in either ``occupation`` or
``short_descriptor``. Two evidence-LLM checks then ask the witness
panel whether the prose / dialogue surrounding each NPC reads as
coherent with the requested role.
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
from benchmarks.scenarios._shared import EVIDENCE_QUOTE_CHAR_BUDGET
from models.game_state import GameState
from models.npc_card import NPCCard

_BEGGAR_SYNONYMS: tuple[str, ...] = ("beggar", "mendicant", "pauper", "almsman")
_SENATOR_SYNONYMS: tuple[str, ...] = ("senator", "patrician", "consul", "magistrate")
_BLINDNESS_MARKERS: tuple[str, ...] = ("blind", "sightless", "milky eyes", "clouded eyes", "unseeing")

_SCENARIO_BRIEF = (
    "In an Ancient-Rome scenario the player visits the steps of the Temple of Vesta — a market "
    "plaza seeded with one open world thread that names two NPCs the engine should materialise: "
    "a blind beggar who haunts the steps, and a Roman senator who visits weekly to give alms. "
    "The captured turns include the player approaching the beggar, greeting him, then waiting "
    "for the senator's arrival."
)


def _npc_haystack(npc: NPCCard) -> str:
    """Compose occupation + short_descriptor + biography + appearance for matching."""
    return " ".join(
        (
            npc.occupation.lower(),
            npc.short_descriptor.lower(),
            npc.biography.lower(),
            npc.appearance.lower(),
        ),
    )


def _find_npc_matching(
    snapshot: GameState,
    role_synonyms: tuple[str, ...],
) -> NPCCard | None:
    """Return the first NPC whose card fields contain any of the role synonyms."""
    for npc in snapshot.npcs.values():
        haystack = _npc_haystack(npc)
        if any(token in haystack for token in role_synonyms):
            return npc
    return None


def _build_role_check_result(
    npc: NPCCard | None,
    role_label: str,
    extra_markers: tuple[str, ...] = (),
    extra_label: str = "",
) -> DeterministicResult:
    """Render the role-tagged deterministic result for a NPC card lookup."""
    if npc is None:
        return DeterministicResult(
            awarded=0,
            reason="no {0} NPC materialised across the run".format(role_label),
        )
    if not extra_markers:
        return DeterministicResult(
            awarded=2,
            reason="{0} NPC materialised: {1}".format(role_label, npc.name),
            evidence_quote=(npc.occupation or "")[:EVIDENCE_QUOTE_CHAR_BUDGET],
        )
    if any(marker in _npc_haystack(npc) for marker in extra_markers):
        return DeterministicResult(
            awarded=2,
            reason="{0} NPC materialised with {1} marker: {2}".format(role_label, extra_label, npc.name),
            evidence_quote=(npc.appearance or "")[:EVIDENCE_QUOTE_CHAR_BUDGET],
        )
    return DeterministicResult(
        awarded=1,
        reason="{0} NPC materialised but no {1} marker on the card: {2}".format(
            role_label,
            extra_label,
            npc.name,
        ),
        evidence_quote=(npc.appearance or "")[:EVIDENCE_QUOTE_CHAR_BUDGET],
    )


def _beggar_role_tagged(
    _captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """A blind-beggar NPC card with the blindness marker exists in the final snapshot."""
    if not snapshots:
        return DeterministicResult(awarded=0, reason="no snapshots captured")
    beggar = _find_npc_matching(snapshots[-1], _BEGGAR_SYNONYMS)
    return _build_role_check_result(
        beggar,
        role_label="blind-beggar",
        extra_markers=_BLINDNESS_MARKERS,
        extra_label="blindness",
    )


def _senator_role_tagged(
    _captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """A Roman-senator NPC card exists in the final snapshot."""
    if not snapshots:
        return DeterministicResult(awarded=0, reason="no snapshots captured")
    senator = _find_npc_matching(snapshots[-1], _SENATOR_SYNONYMS)
    return _build_role_check_result(senator, role_label="Roman-senator")


ELEMENTS: tuple[Element, ...] = (
    Element(
        id="beggar_role_tagged",
        label="Engine materialises a blind-beggar NPC with the blindness marker",
        base_value=2,
        kind=KIND_DETERMINISTIC,
        check=_beggar_role_tagged,
    ),
    Element(
        id="senator_role_tagged",
        label="Engine materialises a Roman-senator NPC",
        base_value=2,
        kind=KIND_DETERMINISTIC,
        check=_senator_role_tagged,
    ),
    Element(
        id="beggar_persona_matches_role",
        label="Beggar dialogue + description read as a destitute, blind street figure",
        base_value=2,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question=(
                "Across the captured turns, does the dialogue and described behaviour of the "
                "blind beggar read as a destitute, blind person (humility, infirmity, dependence "
                "on alms) rather than as a generic stranger or an inappropriately well-spoken "
                "patrician?"
            ),
            evidence_turn=None,
        ),
    ),
    Element(
        id="senator_persona_matches_role",
        label="Senator dialogue + description carry patrician status",
        base_value=2,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question=(
                "Across the captured turns, does the dialogue and described behaviour of the "
                "Roman senator convey patrician status (formal register, sense of social distance "
                "from the beggar, paternalistic charity) rather than treating the beggar as a "
                "peer or speaking as a common citizen?"
            ),
            evidence_turn=None,
        ),
    ),
)
