"""EventManager — advances game time and resolves scheduled events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from timeline.event import EventEffect, EventStatus, GameEvent

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph
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
        old_clock = self._game_state.game_clock
        self._game_state.advance_clock(hours)
        new_clock = self._game_state.game_clock

        # Gather events that complete within [old_clock, new_clock]
        completed: list[GameEvent] = []
        for ev in self._events:
            if ev.status == EventStatus.PENDING and ev.completes_at <= new_clock and ev.completes_at > old_clock:
                ev.status = EventStatus.COMPLETED
                completed.append(ev)

        # Sort by completion time so effects apply in chronological order
        completed.sort(key=lambda event: event.completes_at)

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
            if ev.status == EventStatus.PENDING and (owner_id is None or ev.owner_id == owner_id)
        ]

    def get_completed_since(self, since_time: float) -> list[GameEvent]:
        """Return events that completed after ``since_time``."""
        return [ev for ev in self._events if ev.status == EventStatus.COMPLETED and ev.completes_at > since_time]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_event(self, event: GameEvent) -> None:
        """Apply an event's effects to the game state."""
        for effect in event.effects:
            self._apply_effect(effect)

    def _apply_effect(self, effect: EventEffect) -> None:
        """Apply a single EventEffect to the game state."""
        apply_fn = self._effect_handlers.get(effect.effect_type.upper())
        if apply_fn:
            apply_fn(effect)
        # SPAWN_NPC is handled at a higher level by the Director
        # (it needs to call the NPC Generator agent)

    @property
    def _effect_handlers(self) -> dict:
        return {
            "MOVE_NPC": self._apply_move_npc,
            "ADD_ITEM": self._apply_add_item,
            "REMOVE_ITEM": self._apply_remove_item,
            "ADD_KNOWLEDGE": self._apply_add_knowledge,
            "CHANGE_ATTRIBUTE": self._apply_change_attribute,
            "REMOVE_NPC": self._apply_remove_npc,
        }

    def _apply_move_npc(self, effect: EventEffect) -> None:
        gs = self._game_state
        npc_id = effect.params.get("npc_id", effect.target_id)
        to_loc = effect.params.get("to_location_id", "")
        npc = gs.npcs.get(npc_id)
        if not npc:
            return
        if npc.location_id and npc.location_id in gs.locations:
            gs.locations[npc.location_id].remove_npc(npc_id)
        npc.location_id = to_loc
        loc_obj = gs.locations.get(to_loc)
        if loc_obj:
            loc_obj.add_npc(npc_id)
        if gs.current_scene and gs.current_scene.location_id == npc.location_id:
            from models.scene import SceneNPC

            already = any(snpc.uuid == npc_id for snpc in gs.current_scene.npcs_present)
            if not already:
                gs.current_scene.npcs_present.append(SceneNPC(role=npc.occupation or npc.name, uuid=npc_id))

    def _apply_add_item(self, effect: EventEffect) -> None:
        npc_id = effect.params.get("npc_id", effect.target_id)
        inventory_item = effect.params.get("item", "")
        npc = self._game_state.npcs.get(npc_id)
        if npc and inventory_item:
            npc.add_item_to_inventory(inventory_item)

    def _apply_remove_item(self, effect: EventEffect) -> None:
        npc_id = effect.params.get("npc_id", effect.target_id)
        inventory_item = effect.params.get("item", "")
        npc = self._game_state.npcs.get(npc_id)
        if npc and inventory_item and inventory_item in npc.inventory:
            npc.remove_item_from_inventory(inventory_item)

    def _apply_add_knowledge(self, effect: EventEffect) -> None:
        from knowledge.node import KnowledgeNode, KnowledgeScope, KnowledgeSource

        knowledge_text = effect.params.get("content", "")
        scope_str = effect.params.get("scope", "local")
        tags = effect.params.get("tags", [])
        if knowledge_text:
            node = KnowledgeNode(
                content=knowledge_text,
                scope=KnowledgeScope(scope_str),
                source=KnowledgeSource.FACT,
                tags=tags,
                location_id=effect.params.get("location_id"),
            )
            self._graph.add_node(node)

    def _apply_change_attribute(self, effect: EventEffect) -> None:
        target = self._game_state.npcs.get(effect.target_id)
        attr = effect.params.get("attribute", "")
        attribute_value = effect.params.get("value", 0)
        if target and attr:
            target.update_attribute(attr, attribute_value)

    def _apply_remove_npc(self, effect: EventEffect) -> None:
        gs = self._game_state
        npc_id = effect.target_id
        npc = gs.npcs.get(npc_id)
        if not npc:
            return
        if npc.location_id and npc.location_id in gs.locations:
            gs.locations[npc.location_id].remove_npc(npc_id)
        if gs.current_scene:
            gs.current_scene.npcs_present = [snpc for snpc in gs.current_scene.npcs_present if snpc.uuid != npc_id]
        gs.npcs.pop(npc_id)

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
                effects=[EventEffect(**eff) for eff in follow_up_data.get("effects", [])],
                follow_up_events=follow_up_data.get("follow_up_events", []),
                on_complete_description=follow_up_data.get("on_complete_description", ""),
            )
            self.schedule(follow_up)
