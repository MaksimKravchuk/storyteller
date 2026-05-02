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
from uuid import UUID

from knowledge.hearsay import HearsayDraft, write_hearsay_node
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
    told_by: UUID
    game_time: float
    recipients: list[tuple[UUID, UUID]]


def propagate_rumors(
    graph: KnowledgeGraph,
    game_state: GameState,
    events: list[GameEvent],
) -> list[UUID]:
    """Transmit CITY+ events to non-witness NPCs in the same city.

    For each eligible event, a HEARSAY ``KnowledgeNode`` is added for
    every non-witness NPC that shares the event's city, together with
    a ``TOLD_BY`` edge from the new node back to the originating
    witness. LOCAL-scope events and events without witnesses are
    skipped.

    Returns the list of created HEARSAY node UUIDs so the caller can
    log or assert over them.
    """
    created_ids: list[UUID] = []
    for event in events:
        rumor = _rumor_from_event(game_state, event)
        if rumor is not None:
            created_ids.extend(_write_rumor_hearsay(graph, rumor))
    return created_ids


def _write_rumor_hearsay(graph: KnowledgeGraph, rumor: _Rumor) -> list[UUID]:
    """Write one HEARSAY node per recipient for a single ``_Rumor`` payload."""
    return [
        write_hearsay_node(
            graph,
            HearsayDraft(
                text=rumor.text,
                told_by=rumor.told_by,
                game_time=rumor.game_time,
                recipient_id=npc_id,
                recipient_location=npc_location,
            ),
        )
        for npc_id, npc_location in rumor.recipients
    ]


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
