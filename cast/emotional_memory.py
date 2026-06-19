"""Deterministic emotional-state derivation for NPCs (no LLM) — public facade.

Reads the *unfiltered* personal-memory set an NPC holds (via
:meth:`knowledge.graph.KnowledgeGraph.personal_memories_for`, never the
education/scope-filtered query path, so an NPC's own traces are never
invisible to its own feelings), applies lazy read-time charge decay and
the NPC's values vector, and produces a mood label plus relationship
drift toward every subject it holds charged memories about.

Mood derivation lives in :mod:`cast._mood_derivation`; relationship drift
in :mod:`cast._relationship_drift`. Both are re-exported here so callers
and tests have a single entry point. See the emotional-memory decision
record.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cast._mood_derivation import derive_mood, has_emotional_signal
from cast._relationship_drift import drift_relationships
from cast.hostility import apply_derived_mood

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph
    from models.npc_card import NPCCard


def apply_emotional_state(
    npc: NPCCard,
    graph: KnowledgeGraph,
    now: float,
    *,
    turn: int | None = None,
) -> str:
    """Derive and apply this NPC's mood + relationship drift, returning the mood.

    Mood is only written when the NPC has live (non-decayed) emotional
    signal, so a memory-less or fully-decayed NPC keeps the mood the
    scene/LLM assigned rather than being flattened to neutral.
    """
    memories = graph.personal_memories_for(npc.uuid)
    mood = derive_mood(npc, memories, now)
    if has_emotional_signal(memories, now):
        apply_derived_mood(npc, mood)
    drift_relationships(npc, memories, now, turn=turn)
    return mood
