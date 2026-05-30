"""Builder for the web API's ``WorldView`` payload.

Projects the world around the player — current location, connected locations,
breadcrumb hierarchy, the people present in the current scene, and the game
clock — into the stable ``WorldView`` DTO exposed on both ``GameSnapshot`` and
``ActionResponse``. Mirrors :mod:`interfaces.web.character` so the service layer
stays thin and the shape of the dashboard panels lives next to the schemas.

Unlike ``character.py`` there is no runtime enum on this path: ``location_type``
is already collapsed to a fixed slug set by the ``Location`` model and
``time_of_day`` is a derived label, so no ``_SOURCE_WIRE``-style projection map
is needed here.
"""

from __future__ import annotations

from models.game_state import GameState
from models.location import Location
from models.scene import SceneNPC

from interfaces.web.world_schemas import LocationNode, MapView, ScenePerson, WorldClock, WorldView

# Defensive caps for walking the location hierarchy — a malformed parent chain
# (cycle or absurd depth) must never hang the request.
_HOURS_PER_DAY = 24
_FIRST_DAY = 1
_MAX_BREADCRUMB_DEPTH = 8


def _location_node(location: Location) -> LocationNode:
    """Project a ``Location`` into a map node."""
    return LocationNode(
        id=str(location.uuid),
        name=location.name,
        location_type=location.location_type,
    )


def _connections(game_state: GameState, current: Location) -> list[LocationNode]:
    """Resolve the current location's neighbours, sorted by name.

    Skips connected UUIDs that no longer resolve to a materialised location
    (the same defensive discipline ``character.py`` uses for evicted NPCs).
    """
    nodes: list[LocationNode] = []
    for loc_id in current.connected_locations:
        neighbour = game_state.locations.get(loc_id)
        if neighbour is not None:
            nodes.append(_location_node(neighbour))
    return sorted(nodes, key=lambda node: node.name)


def _breadcrumb(game_state: GameState, current: Location) -> list[LocationNode]:
    """Walk the parent chain from ``current`` outward, outermost first.

    Excludes ``current`` itself. Guards against cycles (a visited set) and
    pathological depth (``_MAX_BREADCRUMB_DEPTH``) so a malformed
    ``parent_location_id`` graph can never loop forever.
    """
    ancestors: list[LocationNode] = []
    visited = {current.uuid}
    parent_id = current.parent_location_id
    while parent_id is not None and len(ancestors) < _MAX_BREADCRUMB_DEPTH:
        if parent_id in visited:
            break
        parent = game_state.locations.get(parent_id)
        if parent is None:
            break
        visited.add(parent_id)
        ancestors.append(_location_node(parent))
        parent_id = parent.parent_location_id
    ancestors.reverse()
    return ancestors


def _map_view(game_state: GameState) -> MapView:
    """Build the map: current location plus neighbours and breadcrumb."""
    location_id = game_state.player.location_id
    current = game_state.locations.get(location_id) if location_id else None
    if current is None:
        return MapView(current=None, connections=[], breadcrumb=[])
    return MapView(
        current=_location_node(current),
        connections=_connections(game_state, current),
        breadcrumb=_breadcrumb(game_state, current),
    )


def _scene_person(game_state: GameState, scene_npc: SceneNPC) -> ScenePerson:
    """Project one scene NPC, routing all name-gating through ``label_for_player``.

    Falls back to the scene role when the ``SceneNPC`` has no generated card
    yet, so an un-materialised role still shows up as a stranger.
    """
    card = game_state.npcs.get(scene_npc.uuid) if scene_npc.uuid else None
    if card is None:
        return ScenePerson(label=scene_npc.role, role=scene_npc.role, known=False)
    return ScenePerson(
        label=card.label_for_player(game_state, scene_npc.role),
        role=scene_npc.role,
        known=scene_npc.uuid in game_state.player.known_npcs,
    )


def _people(game_state: GameState) -> list[ScenePerson]:
    """Project the NPCs present in the current scene (empty when no scene)."""
    scene = game_state.current_scene
    if scene is None:
        return []
    return [_scene_person(game_state, scene_npc) for scene_npc in scene.npcs_present]


def build_world_view(game_state: GameState) -> WorldView:
    """Build the ``WorldView`` payload for the given game state."""
    clock = game_state.game_clock
    return WorldView(
        map=_map_view(game_state),
        people=_people(game_state),
        clock=WorldClock(
            day=int(clock // _HOURS_PER_DAY) + _FIRST_DAY,
            time_of_day=game_state.game_time,
            hour=int(clock % _HOURS_PER_DAY),
        ),
    )
