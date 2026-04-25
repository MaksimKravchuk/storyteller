"""Time and event processing helpers for Director."""

from __future__ import annotations

import asyncio
from cast.schemas.chronicler_response import ScheduledEventDraft
from knowledge.memory import MemoryManager
from knowledge.node import KnowledgeScope
from knowledge.rumor import propagate_rumors
from models.game_state import GameState
from timeline.event import GameEvent
from timeline.event_manager import EventManager
from timeline.time_costs import resolve_time_cost


class EventProcessor:
    """Handles game clock advancement and event resolution."""

    def __init__(
        self,
        game_state: GameState,
        event_manager: EventManager,
        memory_manager: MemoryManager,
    ) -> None:
        self._gs = game_state
        self._event_mgr = event_manager
        self._memory_mgr = memory_manager

    def advance_and_resolve(self, action_type: str, time_override: float | None) -> tuple[list[GameEvent], float]:
        """Advance the game clock and return ``(completed_events, hours_advanced)``."""
        hours = resolve_time_cost(action_type, time_override)
        return self._event_mgr.advance_time(hours), hours

    def schedule_drafts(self, drafts: list[ScheduledEventDraft], now: float) -> list[str]:
        """Turn Chronicler-produced drafts into real :class:`GameEvent`s.

        Each draft becomes a :class:`GameEvent` scheduled ``draft.hours_from_now``
        hours after ``now`` (taken from the caller's current game clock).
        ``GameEvent`` derives its ``completes_at`` from ``scheduled_at +
        duration`` via a pydantic model validator, so we only set
        ``scheduled_at`` and ``duration`` explicitly. Returns the list
        of newly scheduled event UUIDs for logging.
        """
        scheduled_uuids: list[str] = []
        for draft in drafts:
            event = GameEvent(
                name=draft.name,
                scheduled_at=now,
                duration=draft.hours_from_now,
                location_id=draft.location_id,
                scope=draft.scope,
                on_complete_description=draft.on_complete_description,
            )
            scheduled_uuids.append(self._event_mgr.schedule(event))
        return scheduled_uuids

    def partition_events(self, events: list[GameEvent]) -> tuple[list[GameEvent], list[GameEvent]]:
        """Split events into local (visible to player) and remote."""
        player_loc = self._gs.player.location_id
        local: list[GameEvent] = []
        remote: list[GameEvent] = []
        for ev in events:
            if ev.location_id == player_loc:
                local.append(ev)
            else:
                remote.append(ev)
        return local, remote

    async def process_remote_events(self, events: list[GameEvent]) -> None:
        """Feed remote events into the memory system as rumours."""
        await asyncio.gather(
            *(self._memory_mgr.create_memory_from_event(**self.build_memory_kwargs(ev)) for ev in events),
        )

    def propagate_rumors_for_turn(self, events: list[GameEvent]) -> list[str]:
        """Fan completed CITY+ events out to non-witness NPCs in the same city."""
        return propagate_rumors(self._gs.knowledge_graph, self._gs, events)

    def build_memory_kwargs(self, ev: GameEvent) -> dict:
        """Build keyword arguments for create_memory_from_event."""
        scope = _scope_from_string(ev.scope)
        witnesses: list[str] = []
        locations = self._gs.locations
        if ev.location_id and ev.location_id in locations:
            witnesses = list(locations[ev.location_id].npcs_present)
        return {
            "event_description": ev.on_complete_description or ev.name,
            "witness_ids": witnesses,
            "scope": scope,
            "location_id": ev.location_id,
            "game_time": self._gs.game_clock,
        }


def _scope_from_string(scope_str: str) -> KnowledgeScope:
    """Convert a scope string to a KnowledgeScope enum."""
    scope_map = {
        "local": KnowledgeScope.LOCAL,
        "city": KnowledgeScope.CITY,
        "region": KnowledgeScope.REGION,
        "country": KnowledgeScope.COUNTRY,
        "world": KnowledgeScope.WORLD,
    }
    return scope_map.get(scope_str, KnowledgeScope.LOCAL)
