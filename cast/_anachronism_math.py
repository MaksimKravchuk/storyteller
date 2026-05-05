"""Pure helpers for the anachronism modifier math + prompt rendering.

Lives outside :mod:`cast.anachronism` so that module stays under the
WPS202 module-member budget while keeping the math itself easy to
unit test in isolation. Nothing here is async — everything reads from
the cached classifier verdict + per-NPC attributes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cast._anachronism_seeds import ANACHRONISM_CONCEPT_SEEDS
from cast.schemas.anachronism import (
    STRANGENESS_MAX,
    STRANGENESS_MIN,
    AnachronismClassification,
    NPCAnachronismResult,
)

if TYPE_CHECKING:
    from knowledge.query import KnowledgeQueryEngine

# Per-NPC modifier constants.
# Education slides the modifier symmetrically around the canonical
# midpoint of 5: a scholar (8) pays 0.7×, a peasant (2) pays 1.3×.
# At 5 the multiplier is 1, so the prior behaviour (no education
# pull) is the natural fixed point.
_EDUCATION_MIDPOINT = 5
_EDUCATION_HALF_RANGE = 10
# Each prior encounter discounts familiarity by 0.25; the floor of
# 0.2 keeps a sliver of residual oddness so a hundred encounters
# don't normalise the concept entirely (the player is still using
# magic, even if the guard has stopped flinching).
_FAMILIARITY_PER_ENCOUNTER = 0.25
_FAMILIARITY_FLOOR = 0.2
DEFAULT_EDUCATION = 5

INVENTORY_PLACEHOLDER = "(nothing)"


def empty_classification() -> AnachronismClassification:
    """Sentinel verdict used when the classifier is skipped or fails."""
    return AnachronismClassification(
        strangeness_score=0,
        unfamiliar_concepts=[],
        perceived_rewrite="",
    )


def format_inventory(inventory_items: list[str]) -> str:
    """Render the player's inventory for the classifier prompt."""
    return ", ".join(inventory_items) if inventory_items else INVENTORY_PLACEHOLDER


def format_seeds() -> str:
    """Render the canonical concept-seed pool as a bulleted block."""
    return "\n".join("- {0}".format(slug) for slug in ANACHRONISM_CONCEPT_SEEDS)


def compute_effective_strangeness(
    base_score: int,
    education: int,
    encounter_count: int,
) -> int:
    """Apply education + familiarity scaling to ``base_score``.

    A scholar (``education=8``) discounts the base; a peasant
    (``education=2``) amplifies it. Each prior encounter with any of
    the unfamiliar concepts trims familiarity by
    :data:`_FAMILIARITY_PER_ENCOUNTER`, with a hard floor of
    :data:`_FAMILIARITY_FLOOR` so the modifier never hits zero. The
    final value is rounded to int and clamped to ``[0, 10]`` so a
    pathological combination cannot wrap the dice bonus into nonsense.
    """
    education_factor = 1 + (_EDUCATION_MIDPOINT - education) / _EDUCATION_HALF_RANGE
    familiarity_factor = max(
        _FAMILIARITY_FLOOR,
        1 - _FAMILIARITY_PER_ENCOUNTER * encounter_count,
    )
    scaled = round(base_score * education_factor * familiarity_factor)
    return max(STRANGENESS_MIN, min(STRANGENESS_MAX, scaled))


def encounter_count_for_npc(
    npc_id: Any,
    concepts: list[str],
    query_engine: KnowledgeQueryEngine,
) -> int:
    """Aggregate familiarity across the turn's concept tags.

    The classifier returns a list of concepts in one verdict; the
    NPC's prior exposure may be uneven (they have seen flashlights
    before but never a smartphone). Most-novel-wins via ``min`` so the
    turn's strangeness is anchored by the concept the NPC has met
    *least* often — a familiar gadget cannot mask a brand-new one.
    """
    if not concepts:
        return 0
    return min(len(query_engine.get_memories_about_concept(npc_id, concept)) for concept in concepts)


def build_npc_result(
    base: AnachronismClassification,
    npc: Any,
    query_engine: KnowledgeQueryEngine,
) -> NPCAnachronismResult:
    """Apply per-NPC education + familiarity to ``base`` and return the modulated view."""
    education = npc.get_attribute("education", DEFAULT_EDUCATION)
    encounter_count = encounter_count_for_npc(npc.uuid, base.unfamiliar_concepts, query_engine)
    effective = compute_effective_strangeness(
        base.strangeness_score,
        education,
        encounter_count,
    )
    return NPCAnachronismResult(
        base=base,
        effective_strangeness=effective,
        encounter_count=encounter_count,
    )
