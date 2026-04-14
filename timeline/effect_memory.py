"""Effect-driven witness memory writes for EffectApplier.

When an EventEffect mutates NPC state (inventory, status, location,
...), this module emits graph memories so that co-located NPCs can
later recall the event via ``KnowledgeQueryEngine.get_memories_about``.
The per-effect planners live in :mod:`timeline.effect_memory_plans`
and the graph-write primitives live in
:mod:`timeline.effect_memory_write`; this module just wires the two
together behind ``capture_pre_state`` + ``emit_memory``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from knowledge.node import KnowledgeScope
from timeline.effect_memory_plans import plan_memory
from timeline.effect_memory_write import (
    WitnessWrite,
    co_located_witnesses,
    write_witness_memories,
)
from timeline.event import EventEffect

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph
    from models.game_state import GameState


@dataclass(frozen=True)
class EffectPreState:
    """Target NPC state captured before an effect runs.

    ``MOVE_NPC`` mutates ``location_id`` and ``REMOVE_NPC`` pops the NPC
    from game state; without this pre-capture, the memory emitter would
    have no way to resolve the original departure location or name when
    composing witness text after the handler finishes.
    """

    npc_id: str = ""
    npc_name: str = ""
    location_id: str | None = None


def capture_pre_state(game_state: GameState, effect: EventEffect) -> EffectPreState:
    """Snapshot the target NPC before the handler mutates or removes it."""
    npc_id = effect.effect_data.get("npc_id") or effect.target_id
    npc = game_state.npcs.get(npc_id)
    if npc is None:
        return EffectPreState()
    return EffectPreState(npc_id=npc_id, npc_name=npc.name, location_id=npc.location_id)


def emit_memory(
    game_state: GameState,
    graph: KnowledgeGraph,
    effect: EventEffect,
    pre: EffectPreState,
) -> None:
    """Emit witness memories for ``effect``, if any.

    Silent when the target NPC was missing (empty pre-state), when the
    effect type has no planner entry (``ADD_KNOWLEDGE``, ``SPAWN_NPC``,
    unknown), or when a LOCAL-scope effect finds no co-located
    witnesses. CITY-scope effects still emit the wider rumor even
    without witnesses, because the whole point is that the event
    leaves a trace beyond the immediate scene.
    """
    if not pre.npc_id:
        return
    plan = plan_memory(effect, pre.npc_name)
    if plan is None:
        return
    text, scope = plan
    witness_ids = co_located_witnesses(game_state, pre.location_id, pre.npc_id)
    if not witness_ids and scope == KnowledgeScope.LOCAL:
        return
    write_witness_memories(
        graph,
        WitnessWrite(
            text=text,
            witness_ids=witness_ids,
            scope=scope,
            location_id=pre.location_id,
            game_time=game_state.game_clock,
        ),
    )
