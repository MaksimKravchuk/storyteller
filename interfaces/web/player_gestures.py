"""Resolve a structured player gesture into a localized action phrase.

A :class:`~interfaces.web.schemas.PlayerGesture` is a language-neutral tap
on an in-prose entity or a map place: ``{intent, entity_kind, entity_id}``.
This module turns it into the natural-language action the existing turn
pipeline already understands (e.g. ``"talk to Marcus"`` / ``"поговорить с
Марк"``), composed in the *session language* — never an English verb baked
into the engine contract (ADR-0006 / ADR-0010).

Targets are resolved against **persisted** current state — the scene's
``npcs_present`` / ``points_of_interest`` and the location's
``object_states`` — **not** ``game_state.last_visible_entities``, which is
not persisted and is empty after ``resume_session``. NPC naming routes
solely through :meth:`NPCCard.label_for_player` (ADR-0006 §5), so a
stranger's un-introduced name is never leaked into the composed phrase.
"""

from __future__ import annotations

from models.game_state import GameState

from cast.player_gesture_phrases import get_gesture_phrases
from interfaces.web.schemas import PlayerGesture
from interfaces.web.world import build_world_view


class GestureResolutionError(Exception):
    """A gesture's target could not be resolved against current game state.

    Raised for an unknown/stale/no-longer-visible ``entity_id`` (or a
    missing scene). The route layer maps this to HTTP 422.
    """


def compose_player_gesture(game_state: GameState, language: str, gesture: PlayerGesture) -> str:
    """Resolve ``gesture`` to a localized player action phrase.

    Raises :class:`GestureResolutionError` if the target cannot be
    resolved against the current scene / location / map.
    """
    resolvers = {
        "npc": _resolve_npc,
        "poi": _resolve_poi,
        "item": _resolve_item,
        "location": _resolve_location,
    }
    name = resolvers[gesture.entity_kind](game_state, gesture.entity_id)
    phrases = get_gesture_phrases(language)
    template = {
        "examine": phrases.examine,
        "talk": phrases.talk,
        "attack": phrases.attack,
        "steal": phrases.steal,
        "move": phrases.move,
    }[gesture.intent]
    return template.format(name)


def _require_scene(game_state: GameState):
    scene = game_state.current_scene
    if scene is None:
        raise GestureResolutionError("no active scene to resolve a gesture against")
    return scene


def _resolve_npc(game_state: GameState, entity_id: str) -> str:
    """Resolve an NPC tap to its player-visible label (name-gated)."""
    scene = _require_scene(game_state)
    for scene_npc in scene.npcs_present:
        if scene_npc.uuid is not None and str(scene_npc.uuid) == entity_id:
            card = game_state.npcs.get(scene_npc.uuid)
            if card is None:
                return scene_npc.role
            return card.label_for_player(game_state, scene_npc.role)
    raise GestureResolutionError(f"npc '{entity_id}' is not in the current scene")


def _resolve_poi(game_state: GameState, entity_id: str) -> str:
    scene = _require_scene(game_state)
    for poi in scene.points_of_interest:
        if str(poi.uuid) == entity_id:
            return poi.primary_name
    raise GestureResolutionError(f"point of interest '{entity_id}' is not in the current scene")


def _resolve_item(game_state: GameState, entity_id: str) -> str:
    scene = _require_scene(game_state)
    location = game_state.locations.get(scene.location_id)
    object_states = getattr(location, "object_states", None) or {}
    if entity_id in object_states:
        return entity_id
    raise GestureResolutionError(f"item '{entity_id}' is not present at the current location")


def _resolve_location(game_state: GameState, entity_id: str) -> str:
    """Resolve a map place to its name, gated by what the map currently shows."""
    world_map = build_world_view(game_state).map
    nodes = [*world_map.breadcrumb, *world_map.connections]
    if world_map.current is not None:
        nodes.append(world_map.current)
    for node in nodes:
        if node.id == entity_id:
            return node.name
    raise GestureResolutionError(f"location '{entity_id}' is not reachable from the current map")
