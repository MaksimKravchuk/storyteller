"""Internal helpers that turn a memory plan into graph nodes and edges.

Extracted from :mod:`timeline.effect_memory` so each module keeps a
small public surface — the planner code lives next door, the actual
graph write lives here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from knowledge.node import (
    CanonSource,
    EdgeType,
    KnowledgeNode,
    KnowledgeScope,
    KnowledgeSource,
)

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph
    from models.game_state import GameState


@dataclass(frozen=True)
class WitnessWrite:
    """Parameters for a single effect-driven graph write.

    Bundled into a dataclass so ``write_witness_memories`` keeps its
    argument count within WPS211 limits while still carrying everything
    a memory node needs: the free-form ``text``, the set of witnessing
    NPC UUIDs, the event ``scope`` (LOCAL stays private, CITY+ also
    emits a broader rumor/fact node), the anchor ``location_id`` and the
    ``game_time`` at which the effect fired.
    """

    text: str
    witness_ids: list[str]
    scope: KnowledgeScope
    location_id: str | None
    game_time: float


def co_located_witnesses(
    game_state: GameState,
    location_id: str | None,
    exclude_id: str,
) -> list[str]:
    """Return NPC UUIDs at ``location_id`` excluding ``exclude_id``.

    Returns an empty list when the location is unknown or missing, so
    effects on NPCs that are not tracked in ``game_state.locations``
    simply skip witness emission rather than raising.
    """
    if not location_id:
        return []
    location = game_state.locations.get(location_id)
    if location is None:
        return []
    return [npc_id for npc_id in location.npcs_present if npc_id != exclude_id]


def write_witness_memories(graph: KnowledgeGraph, write: WitnessWrite) -> None:
    """Persist a memory to the graph: wider rumor/fact node + personal nodes.

    CITY / REGION scope writes produce a RUMOR node at the requested
    scope; COUNTRY / WORLD scope produce a FACT node. Every listed
    witness additionally receives a LOCAL PERSONAL_EXPERIENCE node
    linked back via a ``WITNESSED`` edge so ``get_memories_about``
    can surface it on subsequent turns.
    """
    if write.scope != KnowledgeScope.LOCAL:
        _write_wider_node(graph, write)
    for witness_id in write.witness_ids:
        personal_id = graph.add_node(
            KnowledgeNode(
                text=write.text,
                scope=KnowledgeScope.LOCAL,
                source=KnowledgeSource.PERSONAL_EXPERIENCE,
                canon=CanonSource.SESSION,
                location_id=write.location_id,
                timestamp=write.game_time,
            ),
        )
        graph.add_edge(witness_id, personal_id, EdgeType.WITNESSED)


def _write_wider_node(graph: KnowledgeGraph, write: WitnessWrite) -> None:
    wider_source = KnowledgeSource.FACT if write.scope >= KnowledgeScope.COUNTRY else KnowledgeSource.RUMOR
    graph.add_node(
        KnowledgeNode(
            text=write.text,
            scope=write.scope,
            source=wider_source,
            canon=CanonSource.SESSION,
            location_id=write.location_id,
            timestamp=write.game_time,
        ),
    )
