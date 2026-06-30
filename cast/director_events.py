"""Time and event processing helpers for Director."""

from __future__ import annotations

from uuid import UUID

from cast._npc_social_events import process_remote_event_memories
from cast.schemas.chronicler_response import ScheduledEventDraft, ScheduledEventEffectDraft
from knowledge import memory as memory_mod
from knowledge import salience as salience_presets
from knowledge.node import KnowledgeScope
from knowledge.rumor import propagate_rumors
from models.game_state import GameState
from timeline.event import EventEffect, GameEvent
from timeline.event_manager import EventManager
from timeline.time_costs import resolve_time_cost


class EventProcessor:
    """Handles game clock advancement and event resolution."""

    def __init__(
        self,
        game_state: GameState,
        event_manager: EventManager,
        memory_manager: memory_mod.MemoryManager,
    ) -> None:
        self._gs = game_state
        self._event_mgr = event_manager
        self._memory_mgr = memory_manager

    def advance_and_resolve(self, action_type: str, time_override: float | None) -> tuple[list[GameEvent], float]:
        """Advance the game clock and return ``(completed_events, hours_advanced)``."""
        hours = resolve_time_cost(action_type, time_override)
        return self._event_mgr.advance_time(hours), hours

    def schedule_drafts(self, drafts: list[ScheduledEventDraft], now: float) -> list[UUID]:
        """Turn Chronicler-produced drafts into real :class:`GameEvent`s.

        Each draft becomes a :class:`GameEvent` scheduled ``draft.hours_from_now``
        hours after ``now`` (taken from the caller's current game clock).
        ``GameEvent`` derives its ``completes_at`` from ``scheduled_at +
        duration`` via a pydantic model validator, so we only set
        ``scheduled_at`` and ``duration`` explicitly. Returns the list
        of newly scheduled event UUIDs for logging.
        """
        scheduled_uuids: list[UUID] = []
        for draft in drafts:
            event = GameEvent(
                name=draft.name,
                scheduled_at=now,
                duration=draft.hours_from_now,
                location_id=draft.location_id,
                scope=draft.scope,
                on_complete_description=draft.on_complete_description,
                effects=_effects_from_drafts(draft.effects),
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
        """Feed remote events into memory, then apply social write-backs."""
        await process_remote_event_memories(events, self._gs, self._memory_mgr, self.build_memory_event)

    def propagate_rumors_for_turn(self, events: list[GameEvent]) -> list[UUID]:
        """Fan completed CITY+ events out to non-witness NPCs in the same city."""
        return propagate_rumors(self._gs.knowledge_graph, self._gs, events)

    def build_memory_event(self, ev: GameEvent) -> memory_mod.MemoryEvent:
        """Wrap a completed :class:`GameEvent` as a :class:`MemoryEvent`.

        Slots carry the event ``name`` as ``action`` and the
        ``on_complete_description`` (when distinct from ``name``) as
        ``outcome``. Scheduled events do not track a single ``subject``
        — they fire on a clock, not on an actor — so the subject slot
        is left ``None``.
        """
        scope = _scope_from_string(ev.scope)
        witnesses: list[UUID] = []
        locations = self._gs.locations
        if ev.location_id is not None and ev.location_id in locations:
            witnesses = list(locations[ev.location_id].npcs_present)
        return memory_mod.MemoryEvent(
            event_description=ev.on_complete_description or ev.name,
            witness_ids=witnesses,
            scope=scope,
            location_id=ev.location_id,
            game_time=self._gs.game_clock,
            salience=salience_presets.REMOTE_EVENT,
            slots=_slots_from_event(ev),
        )


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


def _effects_from_drafts(drafts: list[ScheduledEventEffectDraft]) -> list[EventEffect]:
    return [
        EventEffect(
            effect_type=draft.effect_type,
            target_id=str(draft.target_id),
            effect_data={
                "actor_id": str(draft.actor_id),
                "target_id": str(draft.target_id),
                "kind": draft.kind,
            },
        )
        for draft in drafts
    ]


def _slots_from_event(ev: GameEvent) -> memory_mod.MemorySlots:
    description = ev.on_complete_description
    return memory_mod.MemorySlots(
        action=ev.name or None,
        outcome=description if description and description != ev.name else None,
    )
