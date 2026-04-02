"""EffectApplier — applies resolved event effects to game state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from timeline.event import EventEffect

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph
    from models.game_state import GameState


def _apply_add_item(game_state: GameState, effect: EventEffect) -> None:
    npc_id = effect.effect_data.get("npc_id", effect.target_id)
    inventory_item = effect.effect_data.get("item", "")
    npc = game_state.npcs.get(npc_id)
    if npc and inventory_item:
        npc.add_item_to_inventory(inventory_item)


def _apply_remove_item(game_state: GameState, effect: EventEffect) -> None:
    npc_id = effect.effect_data.get("npc_id", effect.target_id)
    inventory_item = effect.effect_data.get("item", "")
    npc = game_state.npcs.get(npc_id)
    if npc and inventory_item and inventory_item in npc.inventory:
        npc.remove_item_from_inventory(inventory_item)


def _apply_add_knowledge(graph: KnowledgeGraph, effect: EventEffect) -> None:
    from knowledge.node import KnowledgeNode, KnowledgeScope, KnowledgeSource

    knowledge_text = effect.effect_data.get("content", "")
    scope_str = effect.effect_data.get("scope", "local")
    tags = effect.effect_data.get("tags", [])
    if knowledge_text:
        node = KnowledgeNode(
            text=knowledge_text,
            scope=KnowledgeScope(scope_str),
            source=KnowledgeSource.FACT,
            tags=tags,
            location_id=effect.effect_data.get("location_id"),
        )
        graph.add_node(node)


def _apply_change_attribute(game_state: GameState, effect: EventEffect) -> None:
    target = game_state.npcs.get(effect.target_id)
    attr = effect.effect_data.get("attribute", "")
    attribute_value = effect.effect_data.get("value", 0)
    if target and attr:
        target.update_attribute(attr, attribute_value)


class EffectApplier:
    """Applies event effects to the game world.

    Each supported effect type has a handler method.  Unknown types are
    silently skipped (e.g. ``SPAWN_NPC`` is handled by the Director).
    """

    def __init__(self, game_state: GameState, graph: KnowledgeGraph):
        self._game_state = game_state
        self._graph = graph

    def apply(self, effect: EventEffect) -> None:
        """Apply a single EventEffect to the game state."""
        apply_fn = self._handlers.get(effect.effect_type.upper())
        if apply_fn:
            apply_fn(effect)

    @property
    def _handlers(self) -> dict:
        return {
            "MOVE_NPC": self._move_npc,
            "ADD_ITEM": lambda eff: _apply_add_item(self._game_state, eff),
            "REMOVE_ITEM": lambda eff: _apply_remove_item(self._game_state, eff),
            "ADD_KNOWLEDGE": lambda eff: _apply_add_knowledge(self._graph, eff),
            "CHANGE_ATTRIBUTE": lambda eff: _apply_change_attribute(self._game_state, eff),
            "REMOVE_NPC": self._remove_npc,
        }

    def _move_npc(self, effect: EventEffect) -> None:
        npc_id = effect.effect_data.get("npc_id", effect.target_id)
        npc = self._game_state.npcs.get(npc_id)
        if not npc:
            return
        if npc.location_id and npc.location_id in self._game_state.locations:
            self._game_state.locations[npc.location_id].remove_npc(npc_id)
        npc.location_id = effect.effect_data.get("to_location_id", "")
        new_loc = self._game_state.locations.get(npc.location_id)
        if new_loc:
            new_loc.add_npc(npc_id)
        self._update_scene(npc_id, npc)

    def _update_scene(self, npc_id: str, npc: Any) -> None:
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
        npc_id = effect.target_id
        game_state = self._game_state
        npc = game_state.npcs.get(npc_id)
        if not npc:
            return
        locations = game_state.locations
        if npc.location_id and npc.location_id in locations:
            locations[npc.location_id].remove_npc(npc_id)
        if game_state.current_scene:
            game_state.current_scene.npcs_present = [
                snpc for snpc in game_state.current_scene.npcs_present if snpc.uuid != npc_id
            ]
        game_state.npcs.pop(npc_id)
