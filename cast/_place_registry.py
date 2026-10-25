"""Register new places and keep the travel links between places."""

from __future__ import annotations

from uuid import UUID

from models.game_state import GameState
from models.location import Location
from models.scene import Scene

_PLACE_DESCRIPTION_MAX = 160
_PLACE_NAME_MAX = 60
_UNNAMED_PLACE = "Unnamed place"
_COARSE_LOCATION_TYPES = frozenset(("city", "district", "region", "country"))


def place_for_unknown_scene(game_state: GameState, scene: Scene, allow_new_place: bool) -> UUID:
    """Return the location for a scene the Scene Builder could not match to a known place.

    On a non-travel rebuild the player is still where they were; otherwise
    (or when the player has no place yet) the scene becomes a new ``Location``.
    """
    origin_id = game_state.player.location_id
    origin = game_state.locations.get(origin_id) if origin_id else None
    if origin is not None and not allow_new_place:
        return origin.uuid
    location = Location(
        name=_place_name(scene),
        description=scene.description[:_PLACE_DESCRIPTION_MAX],
        parent_location_id=_parent_for(origin),
    )
    game_state.locations[location.uuid] = location
    return location.uuid


def connect(game_state: GameState, origin_id: UUID | None, destination_id: UUID) -> None:
    """Link two distinct known places both ways (idempotent)."""
    locations = game_state.locations
    origin = locations.get(origin_id) if origin_id else None
    destination = locations.get(destination_id)
    if origin is None or destination is None or origin is destination:
        return
    _link(origin, destination.uuid)
    _link(destination, origin.uuid)


def _place_name(scene: Scene) -> str:
    first_sentence = scene.description.split(".")[0]
    return scene.place_name.strip() or first_sentence[:_PLACE_NAME_MAX].strip() or _UNNAMED_PLACE


def _parent_for(origin: Location | None) -> UUID | None:
    """A new place sits inside the origin when it is an area, else beside it."""
    if origin is None:
        return None
    if origin.location_type in _COARSE_LOCATION_TYPES:
        return origin.uuid
    return origin.parent_location_id


def _link(location: Location, other_id: UUID) -> None:
    if other_id not in location.connected_locations:
        location.connected_locations.append(other_id)
