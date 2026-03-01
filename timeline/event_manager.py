"""EventManager — advances game time and resolves scheduled events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from timeline.event import EventEffect, EventStatus, GameEvent

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph
    from knowledge.node import KnowledgeNode, KnowledgeScope, KnowledgeSource
    from models.game_state import GameState


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
        self._graph = knowledge_graph
        self._events: list[GameEvent] = []

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
        old_clock = self._game_state.game_clock
        self._game_state.advance_clock(hours)
        new_clock = self._game_state.game_clock

        # Gather events that complete within [old_clock, new_clock]
        completed: list[GameEvent] = []
        for ev in self._events:
            if (
                ev.status == EventStatus.PENDING
                and ev.completes_at <= new_clock
                and ev.completes_at > old_clock
            ):
                ev.status = EventStatus.COMPLETED
                completed.append(ev)

        # Sort by completion time so effects apply in chronological order
        completed.sort(key=lambda e: e.completes_at)

        # Resolve each completed event
        for ev in completed:
            self._resolve_event(ev)
            self._schedule_follow_ups(ev)

        return completed

    def get_pending_events(self, owner_id: str | None = None) -> list[GameEvent]:
        """Return pending events, optionally filtered by owner NPC."""
        return [
            ev
            for ev in self._events
            if ev.status == EventStatus.PENDING
            and (owner_id is None or ev.owner_id == owner_id)
        ]

    def get_completed_since(self, since_time: float) -> list[GameEvent]:
        """Return events that completed after ``since_time``."""
        return [
            ev
            for ev in self._events
            if ev.status == EventStatus.COMPLETED and ev.completes_at > since_time
        ]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_event(self, event: GameEvent) -> None:
        """Apply an event's effects to the game state."""
        for effect in event.effects:
            self._apply_effect(effect)

    def _apply_effect(self, effect: EventEffect) -> None:
        """Apply a single EventEffect to the game state."""
        gs = self._game_state
        etype = effect.effect_type.upper()

        if etype == "MOVE_NPC":
            npc_id = effect.params.get("npc_id", effect.target_id)
            to_loc = effect.params.get("to_location_id", "")
            npc = gs.npcs.get(npc_id)
            if npc:
                # Remove from old location
                if npc.location_id and npc.location_id in gs.locations:
                    gs.locations[npc.location_id].remove_npc(npc_id)
                # Move to new location
                npc.location_id = to_loc
                if to_loc in gs.locations:
                    gs.locations[to_loc].add_npc(npc_id)
                # Update current scene if applicable
                if gs.current_scene and gs.current_scene.location_id == npc.location_id:
                    if npc_id not in gs.current_scene.npcs_present:
                        gs.current_scene.npcs_present.append(npc_id)

        elif etype == "ADD_ITEM":
            npc_id = effect.params.get("npc_id", effect.target_id)
            item = effect.params.get("item", "")
            npc = gs.npcs.get(npc_id)
            if npc and item:
                npc.add_item_to_inventory(item)

        elif etype == "REMOVE_ITEM":
            npc_id = effect.params.get("npc_id", effect.target_id)
            item = effect.params.get("item", "")
            npc = gs.npcs.get(npc_id)
            if npc and item and item in npc.inventory:
                npc.remove_item_from_inventory(item)

        elif etype == "ADD_KNOWLEDGE":
            # Dynamically import to avoid circular deps at module level
            from knowledge.node import KnowledgeNode, KnowledgeScope, KnowledgeSource

            content = effect.params.get("content", "")
            scope_str = effect.params.get("scope", "local")
            tags = effect.params.get("tags", [])
            if content:
                node = KnowledgeNode(
                    content=content,
                    scope=KnowledgeScope(scope_str),
                    source=KnowledgeSource.FACT,
                    tags=tags,
                    location_id=effect.params.get("location_id"),
                )
                self._graph.add_node(node)

        elif etype == "CHANGE_ATTRIBUTE":
            target = gs.npcs.get(effect.target_id)
            attr = effect.params.get("attribute", "")
            value = effect.params.get("value", 0)
            if target and attr:
                target.update_attribute(attr, value)

        elif etype == "REMOVE_NPC":
            npc_id = effect.target_id
            npc = gs.npcs.get(npc_id)
            if npc:
                if npc.location_id and npc.location_id in gs.locations:
                    gs.locations[npc.location_id].remove_npc(npc_id)
                if gs.current_scene and npc_id in gs.current_scene.npcs_present:
                    gs.current_scene.npcs_present.remove(npc_id)
                del gs.npcs[npc_id]

        elif etype == "CHANGE_MOOD":
            npc_id = effect.params.get("npc_id", effect.target_id)
            mood = effect.params.get("mood", "neutral")
            npc = gs.npcs.get(npc_id)
            if npc:
                npc.current_mood = mood

        elif etype == "UPDATE_ATTITUDE":
            npc_id = effect.params.get("npc_id", effect.target_id)
            target_id = effect.params.get("target_id", "")
            emotion = effect.params.get("emotion", "")
            delta = float(effect.params.get("delta", 0.0))
            npc = gs.npcs.get(npc_id)
            if npc and target_id and emotion:
                if target_id not in npc.emotional_attitudes:
                    npc.emotional_attitudes[target_id] = {}
                current = npc.emotional_attitudes[target_id].get(emotion, 0.0)
                npc.emotional_attitudes[target_id][emotion] = max(
                    -1.0, min(1.0, current + delta)
                )

        # SPAWN_NPC is handled at a higher level by the Director
        # (it needs to call the NPC Generator agent)

    def _schedule_follow_ups(self, event: GameEvent) -> None:
        """Schedule chained events defined in ``event.follow_up_events``."""
        for follow_up_data in event.follow_up_events:
            follow_up = GameEvent(
                name=follow_up_data.get("name", "Follow-up event"),
                scheduled_at=event.completes_at,
                duration=follow_up_data.get("duration", 1.0),
                owner_id=follow_up_data.get("owner_id", event.owner_id),
                location_id=follow_up_data.get("location_id", event.location_id),
                scope=follow_up_data.get("scope", event.scope),
                effects=[
                    EventEffect(**eff)
                    for eff in follow_up_data.get("effects", [])
                ],
                follow_up_events=follow_up_data.get("follow_up_events", []),
                on_complete_description=follow_up_data.get(
                    "on_complete_description", ""
                ),
            )
            self.schedule(follow_up)
