"""EventManager — advances game time and resolves scheduled events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from timeline.effect_applier import EffectApplier
from timeline.event import EventEffect, EventStatus, GameEvent

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph
    from models.game_state import GameState


def _collect_completed(
    events: list[GameEvent],
    clock_before: float,
    clock_after: float,
) -> list[GameEvent]:
    """Mark and return events that completed in [clock_before, clock_after]."""
    completed: list[GameEvent] = []
    for ev in events:
        is_in_window = ev.completes_at <= clock_after and ev.completes_at > clock_before
        if ev.status == EventStatus.PENDING and is_in_window:
            ev.status = EventStatus.COMPLETED
            completed.append(ev)
    completed.sort(key=lambda event: event.completes_at)
    return completed


def _resolve_completed(completed: list[GameEvent], applier: EffectApplier, schedule_fn) -> None:
    """Apply effects and schedule follow-ups for each completed event."""
    for ev in completed:
        for effect in ev.effects:
            applier.apply(effect)
        for follow_up_data in ev.follow_up_events:
            schedule_fn(_build_follow_up(ev, follow_up_data))


def _build_follow_up(event: GameEvent, follow_up_data: dict) -> GameEvent:
    """Build a follow-up GameEvent from serialised data."""
    return GameEvent(
        name=follow_up_data.get("name", "Follow-up event"),
        scheduled_at=event.completes_at,
        duration=follow_up_data.get("duration", 1.0),
        owner_id=follow_up_data.get("owner_id", event.owner_id),
        location_id=follow_up_data.get("location_id", event.location_id),
        scope=follow_up_data.get("scope", event.scope),
        effects=[EventEffect(**eff) for eff in follow_up_data.get("effects", [])],
        follow_up_events=follow_up_data.get("follow_up_events", []),
        on_complete_description=follow_up_data.get("on_complete_description", ""),
    )


class EventManager:
    """Manages the game timeline.

    When the Director determines the time cost of a player action it calls
    ``advance_time(hours)`` which:
      1. Moves the game clock forward.
      2. Finds all events that complete within the new window.
      3. Applies their effects to the game state.
      4. Schedules any follow-up (chained) events.
      5. Returns the list of completed events so the Director/Narrator
         can inform the player about visible ones.
    """

    def __init__(
        self,
        game_state: GameState,
        knowledge_graph: KnowledgeGraph,
    ):
        self._game_state = game_state
        self._applier = EffectApplier(game_state, knowledge_graph)
        self._events: list[GameEvent] = []

    @property
    def all_events(self) -> list[GameEvent]:
        """Return a copy of the events list (for persistence)."""
        return list(self._events)

    @all_events.setter
    def all_events(self, events: list[GameEvent]) -> None:
        """Restore events from persistence."""
        self._events = list(events)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def schedule(self, event: GameEvent) -> str:
        """Add an event to the timeline. Returns the event UUID."""
        self._events.append(event)
        return event.uuid

    def cancel(self, event_id: str) -> bool:
        """Cancel a pending event. Returns True if found and cancelled."""
        for ev in self._events:
            if ev.uuid == event_id and ev.status == EventStatus.PENDING:
                ev.status = EventStatus.CANCELLED
                return True
        return False

    def advance_time(self, hours: float) -> list[GameEvent]:
        """Advance the game clock by ``hours`` and resolve completed events.

        Returns the list of events that completed during this time step,
        sorted by completion time (earliest first).
        """
        clock_before = self._game_state.game_clock
        self._game_state.advance_clock(hours)
        completed = _collect_completed(self._events, clock_before, self._game_state.game_clock)
        _resolve_completed(completed, self._applier, self.schedule)
        return completed

    def get_pending_events(self, owner_id: str | None = None) -> list[GameEvent]:
        """Return pending events, optionally filtered by owner NPC."""
        return [
            ev
            for ev in self._events
            if ev.status == EventStatus.PENDING and (owner_id is None or ev.owner_id == owner_id)
        ]
