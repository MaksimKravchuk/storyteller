"""Keep places and the people in them stable across scene rebuilds.

Every MOVE / SLEEP rebuilds the scene. Without this module each rebuild
landed on a sentinel location and repopulated the scene from free-text
roles, so an NPC the player had talked to was replaced by a freshly
generated stranger (sometimes with the same name) and their memories
became unreachable. Here the Director pins each scene to a ``Location``,
moves the player there, and seats the NPCs who live or work at that place
before any new NPC is generated.
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from cast._place_registry import connect, place_for_unknown_scene
from cast._place_residents import present_residents
from cast._place_seating import seat_residents
from cast._scene_location import UNKNOWN_SCENE_LOCATION
from models.game_state import GameState
from models.scene import Scene

_MAX_KNOWN_PLACES = 20
_PLACE_KEY_LENGTH = 8


def place_key(location_id: UUID) -> str:
    """Return the short id a location is shown under in LLM prompts."""
    return location_id.hex[:_PLACE_KEY_LENGTH]


def resolve_scene_location_id(raw: str | None, known_ids: Iterable[UUID]) -> UUID:
    """Return the known location *raw* names, or the sentinel for a place not seen before.

    Accepts the short :func:`place_key` form and the full UUID string, both
    case-insensitively.
    """
    key = (raw or "").strip().lower()
    if not key:
        return UNKNOWN_SCENE_LOCATION
    for location_id in known_ids:
        if key in {place_key(location_id), str(location_id)}:
            return location_id
    return UNKNOWN_SCENE_LOCATION


def enter_scene(game_state: GameState, scene: Scene, *, allow_new_place: bool) -> None:
    """Pin *scene* to a ``Location``, move the player there and seat its residents.

    ``allow_new_place`` is True when the player travelled (MOVE) or this is
    the first scene; an unrecognised place then becomes a new ``Location``.
    Otherwise (e.g. SLEEP) an unrecognised place means "still here".
    """
    if scene.location_id not in game_state.locations:
        scene.location_id = place_for_unknown_scene(game_state, scene, allow_new_place)
    connect(game_state, game_state.player.location_id, scene.location_id)
    game_state.player.location_id = scene.location_id
    seat_residents(game_state, scene)


def format_known_places(game_state: GameState) -> str:
    """Render the Scene Builder's list of known places with the people there now."""
    current = game_state.player.location_id
    place_ids = list(game_state.locations)[-_MAX_KNOWN_PLACES:]
    if current in game_state.locations and current not in place_ids:
        place_ids.insert(0, current)
    return "\n".join(_known_place_line(game_state, location_id, current) for location_id in place_ids)


def _known_place_line(game_state: GameState, location_id: UUID, current: UUID | None) -> str:
    location = game_state.locations[location_id]
    line = "- id {0}: {1}".format(place_key(location_id), location.name)
    if location_id == current:
        line = "{0} (the player is here now)".format(line)
    residents = present_residents(game_state, location_id)
    people = [npc.label_for_player(game_state, npc.occupation) for npc in residents]
    if people:
        line = "{0} | people here now: {1}".format(line, "; ".join(people))
    return line
