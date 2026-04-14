"""Rumour propagation — transmits CITY+ events to non-witness NPCs.

Runs at scene-change boundaries (called from
``cast.director_execution.PlanExecutor`` after events are processed).
For each completed event with ``scope >= CITY`` that has at least one
witness, every non-witness NPC sharing the event's city receives a
private HEARSAY ``KnowledgeNode``; the node carries a ``TOLD_BY`` edge
back to the originating witness so the chain of transmission is
preserved in the graph.

The hearsay node is LOCAL-scoped at the recipient NPC's current
location, which lets the existing
``KnowledgeQueryEngine.passes_location`` filter gate it to that NPC
without any query-engine changes.
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
from knowledge.rumor_scope import non_witness_city_npcs, witnesses_at

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph
    from models.game_state import GameState
    from timeline.event import GameEvent


_PROPAGATING_SCOPES = frozenset(("city", "region", "country", "world"))


@dataclass(frozen=True)
class _Rumor:
    """Everything needed to write hearsay nodes for a single event.

    Carries the event ``text`` and the ``told_by`` witness that will
    become the ``TOLD_BY`` edge target, plus the ``game_time`` used as
    each hearsay node's timestamp and the pre-computed ``recipients``
    list (``(npc_id, npc_location_id)`` pairs).
    """

    text: str
    told_by: str
    game_time: float
    recipients: list[tuple[str, str]]


def propagate_rumors(
    graph: KnowledgeGraph,
    game_state: GameState,
    events: list[GameEvent],
) -> list[str]:
    """Transmit CITY+ events to non-witness NPCs in the same city.

    For each eligible event, a HEARSAY ``KnowledgeNode`` is added for
    every non-witness NPC that shares the event's city, together with
    a ``TOLD_BY`` edge from the new node back to the originating
    witness. LOCAL-scope events and events without witnesses are
    skipped.

    Returns the list of created HEARSAY node UUIDs so the caller can
    log or assert over them.
    """
    created_ids: list[str] = []
    for event in events:
        rumor = _rumor_from_event(game_state, event)
        if rumor is None:
            continue
        for npc_id, npc_location in rumor.recipients:
            created_ids.append(_write_hearsay_node(graph, rumor, npc_id, npc_location))
    return created_ids


def _rumor_from_event(game_state: GameState, event: GameEvent) -> _Rumor | None:
    """Distill an event into a ``_Rumor`` payload, or ``None`` when ineligible."""
    if not event.location_id or event.scope not in _PROPAGATING_SCOPES:
        return None
    witness_list = witnesses_at(game_state, event.location_id)
    if not witness_list:
        return None
    recipients = non_witness_city_npcs(game_state, event.location_id, witness_list)
    if not recipients:
        return None
    return _Rumor(
        text=event.on_complete_description or event.name,
        told_by=witness_list[0],
        game_time=game_state.game_clock,
        recipients=recipients,
    )


def _write_hearsay_node(
    graph: KnowledgeGraph,
    rumor: _Rumor,
    npc_id: str,
    npc_location: str,
) -> str:
    """Create one LOCAL HEARSAY node for ``npc_id`` and return its UUID.

    The recipient NPC does not get a direct edge to the node — the
    LOCAL scope + ``location_id`` is enough for
    ``KnowledgeQueryEngine`` to surface it in that NPC's context. The
    only edge written is the ``TOLD_BY`` provenance link back to the
    originating witness so the chain of transmission stays auditable.
    The recipient UUID is stored on that edge so tests and callers can
    trace "who heard this" without overloading ``WITNESSED``.
    """
    hearsay = KnowledgeNode(
        text=rumor.text,
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.HEARSAY,
        canon=CanonSource.SESSION,
        location_id=npc_location,
        timestamp=rumor.game_time,
    )
    hearsay_id = graph.add_node(hearsay)
    graph.add_edge(
        hearsay_id,
        rumor.told_by,
        EdgeType.TOLD_BY,
        metadata={"recipient_id": npc_id},
    )
    return hearsay_id
