"""EffectApplier — applies resolved event effects to game state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from loguru import logger

from knowledge.memory_preservation import preserve_departing_npc_memories
from timeline._uuid_coerce import coerce_uuid as _coerce_uuid
from timeline.effect_memory import capture_pre_state, emit_memory
from timeline.event import EventEffect

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph
    from models.game_state import GameState

_KEY_NPC_ID = "npc_id"


def _apply_add_item(game_state: GameState, effect: EventEffect) -> None:
    npc_id = _coerce_uuid(effect.effect_data.get(_KEY_NPC_ID, effect.target_id))
    inventory_item = effect.effect_data.get("item", "")
    if npc_id is None:
        return
    npc = game_state.npcs.get(npc_id)
    if npc and inventory_item:
        npc.add_item_to_inventory(inventory_item)


def _apply_remove_item(game_state: GameState, effect: EventEffect) -> None:
    npc_id = _coerce_uuid(effect.effect_data.get(_KEY_NPC_ID, effect.target_id))
    inventory_item = effect.effect_data.get("item", "")
    if npc_id is None:
        return
    npc = game_state.npcs.get(npc_id)
    if npc and inventory_item and inventory_item in npc.inventory:
        npc.remove_item_from_inventory(inventory_item)


def _apply_add_knowledge(graph: KnowledgeGraph, effect: EventEffect) -> None:
    from knowledge.node import CanonSource, KnowledgeNode, KnowledgeScope, KnowledgeSource

    knowledge_text = effect.effect_data.get("content", "")
    scope_str = effect.effect_data.get("scope", "local")
    tags = effect.effect_data.get("tags", [])
    if knowledge_text:
        node = KnowledgeNode(
            text=knowledge_text,
            scope=KnowledgeScope[scope_str.upper()],
            source=KnowledgeSource.FACT,
            canon=CanonSource.SESSION,
            tags=tags,
            location_id=_coerce_uuid(effect.effect_data.get("location_id")),
        )
        graph.add_node(node)


def _apply_change_attribute(game_state: GameState, effect: EventEffect) -> None:
    target_id = _coerce_uuid(effect.target_id)
    attr = effect.effect_data.get("attribute", "")
    attribute_value = effect.effect_data.get("value", 0)
    if target_id is None:
        return
    target = game_state.npcs.get(target_id)
    if target and attr:
        target.update_attribute(attr, attribute_value)


def _apply_change_status(game_state: GameState, effect: EventEffect) -> None:
    npc_id = _coerce_uuid(effect.effect_data.get(_KEY_NPC_ID, effect.target_id))
    new_status = effect.effect_data.get("status", "")
    if npc_id is None:
        return
    npc = game_state.npcs.get(npc_id)
    if npc and new_status:
        npc.physical_status = new_status


def _apply_object_damage(game_state: GameState, effect: EventEffect) -> None:
    location_id = _coerce_uuid(effect.effect_data.get("location_id") or effect.target_id)
    object_key = effect.effect_data.get("object_key", "")
    state_description = effect.effect_data.get("state_description", "")
    if location_id is None:
        logger.warning(
            "APPLY_OBJECT_DAMAGE dropped: missing location_id (target_id={0})",
            effect.target_id,
        )
        return
    location = game_state.locations.get(location_id)
    if location is None:
        logger.warning(
            "APPLY_OBJECT_DAMAGE dropped: unknown location_id={0} (target_id={1})",
            location_id,
            effect.target_id,
        )
        return
    location.record_object_state(object_key, state_description)


class EffectApplier:
    """Applies event effects to the game world.

    Each supported effect type has a handler method.  Unknown types are
    silently skipped (e.g. ``SPAWN_NPC`` is handled by the Director).
    """

    def __init__(self, game_state: GameState, graph: KnowledgeGraph):
        self._game_state = game_state
        self._graph = graph

    def apply(self, effect: EventEffect) -> None:
        """Apply a single EventEffect to the game state.

        Pre-state is captured before the handler runs so MOVE_NPC and
        REMOVE_NPC can still reference the original location and name
        when emitting witness memories afterwards.
        """
        apply_fn = self._handlers.get(effect.effect_type.upper())
        if not apply_fn:
            return
        pre = capture_pre_state(self._game_state, effect)
        apply_fn(effect)
        emit_memory(self._game_state, self._graph, effect, pre)

    @property
    def _handlers(self) -> dict:
        return {
            "MOVE_NPC": self._move_npc,
            "ADD_ITEM": lambda eff: _apply_add_item(self._game_state, eff),
            "REMOVE_ITEM": lambda eff: _apply_remove_item(self._game_state, eff),
            "ADD_KNOWLEDGE": lambda eff: _apply_add_knowledge(self._graph, eff),
            "CHANGE_ATTRIBUTE": lambda eff: _apply_change_attribute(self._game_state, eff),
            "CHANGE_STATUS": lambda eff: _apply_change_status(self._game_state, eff),
            "APPLY_OBJECT_DAMAGE": lambda eff: _apply_object_damage(self._game_state, eff),
            "REMOVE_NPC": self._remove_npc,
        }

    def _move_npc(self, effect: EventEffect) -> None:
        npc_id = _coerce_uuid(effect.effect_data.get(_KEY_NPC_ID, effect.target_id))
        if npc_id is None:
            return
        npc = self._game_state.npcs.get(npc_id)
        if not npc:
            return
        if npc.location_id is not None and npc.location_id in self._game_state.locations:
            self._game_state.locations[npc.location_id].remove_npc(npc_id)
        npc.location_id = _coerce_uuid(effect.effect_data.get("to_location_id"))
        if npc.location_id is None:
            return
        new_loc = self._game_state.locations.get(npc.location_id)
        if new_loc:
            new_loc.add_npc(npc_id)
        self._update_scene(npc_id, npc)

    def _update_scene(self, npc_id: UUID, npc: Any) -> None:
        """Add a moved NPC to the current scene if they arrived at the scene's location."""
        scene = self._game_state.current_scene
        if not scene or scene.location_id != npc.location_id:
            return
        already_present = any(snpc.uuid == npc_id for snpc in scene.npcs_present)
        if already_present:
            return
        from models.scene import SceneNPC

        npc_role = npc.occupation or npc.name
        scene.npcs_present.append(SceneNPC(role=npc_role, uuid=npc_id))

    def _remove_npc(self, effect: EventEffect) -> None:
        npc_id = _coerce_uuid(effect.target_id)
        if npc_id is None:
            return
        game_state = self._game_state
        npc = game_state.npcs.get(npc_id)
        if not npc:
            return
        # Run preservation BEFORE mutation: once the NPC is popped and
        # their location cleared, the rumor-scope walker has no anchor
        # to resolve same-city listeners and the memories silently rot.
        if npc.location_id is not None:
            preserve_departing_npc_memories(self._graph, game_state, npc_id, npc.location_id)
        locations = game_state.locations
        if npc.location_id is not None and npc.location_id in locations:
            locations[npc.location_id].remove_npc(npc_id)
        if game_state.current_scene:
            game_state.current_scene.npcs_present = [
                snpc for snpc in game_state.current_scene.npcs_present if snpc.uuid != npc_id
            ]
        game_state.npcs.pop(npc_id)
