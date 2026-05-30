"""Unit tests for ``interfaces.web.world.build_world_view``."""

from __future__ import annotations

from uuid import UUID

import allure

from interfaces.web.world import build_world_view
from models.game_state import GameState
from models.location import Location
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from tests._uuid_helpers import make_uuid

_STORY_BUILDER = "World view builder"
_KNOWN_TIME_LABELS = frozenset(("night", "morning", "afternoon", "evening"))

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Web UI"),
]


def _place(
    game_state: GameState,
    name: str,
    location_type: str = "generic",
    parent_location_id: UUID | None = None,
    connected_locations: list[UUID] | None = None,
) -> Location:
    """Build a location, register it on the game state, and return it."""
    location = Location(
        name=name,
        location_type=location_type,
        parent_location_id=parent_location_id,
        connected_locations=connected_locations or [],
    )
    game_state.locations[location.uuid] = location
    return location


def _scene_with(game_state: GameState, location_id: UUID, npcs: list[SceneNPC]) -> None:
    game_state.current_scene = Scene(location_id=location_id, npcs_present=npcs)


@allure.story(_STORY_BUILDER)
@allure.title("build_world_view resolves the current location from player.location_id")
def test_builder_resolves_current_location(game_state: GameState) -> None:
    here = _place(game_state, "Forum Romanum", location_type="district")
    game_state.player.location_id = here.uuid

    current = build_world_view(game_state).map.current

    assert current is not None
    assert current.id == str(here.uuid)
    assert current.name == "Forum Romanum"
    assert current.location_type == "district"


@allure.story(_STORY_BUILDER)
@allure.title("build_world_view returns a null current location when the player has none")
def test_builder_null_current_when_unset(game_state: GameState) -> None:
    game_view = build_world_view(game_state)

    assert game_view.map.current is None
    assert game_view.map.connections == []
    assert game_view.map.breadcrumb == []


@allure.story(_STORY_BUILDER)
@allure.title("build_world_view skips connected locations that no longer resolve")
def test_builder_skips_dangling_connections(game_state: GameState) -> None:
    neighbour = _place(game_state, "The Tavern", location_type="building")
    here = _place(
        game_state,
        "Forum Romanum",
        location_type="district",
        connected_locations=[neighbour.uuid, make_uuid("ghost-location")],
    )
    game_state.player.location_id = here.uuid

    connections = build_world_view(game_state).map.connections

    assert [node.name for node in connections] == ["The Tavern"]


@allure.story(_STORY_BUILDER)
@allure.title("build_world_view sorts connected locations by name")
def test_builder_sorts_connections_by_name(game_state: GameState) -> None:
    zephyr = _place(game_state, "Zephyr Gate", location_type="building")
    alley = _place(game_state, "Alley", location_type="building")
    here = _place(
        game_state,
        "Forum Romanum",
        location_type="district",
        connected_locations=[zephyr.uuid, alley.uuid],
    )
    game_state.player.location_id = here.uuid

    connections = build_world_view(game_state).map.connections

    assert [node.name for node in connections] == ["Alley", "Zephyr Gate"]


@allure.story(_STORY_BUILDER)
@allure.title("build_world_view builds the breadcrumb outermost-first, excluding the current node")
def test_builder_breadcrumb_outermost_first(game_state: GameState) -> None:
    city = _place(game_state, "Rome", location_type="city")
    district = _place(game_state, "Forum", location_type="district", parent_location_id=city.uuid)
    tavern = _place(game_state, "The Tavern", location_type="building", parent_location_id=district.uuid)
    game_state.player.location_id = tavern.uuid

    breadcrumb = build_world_view(game_state).map.breadcrumb

    assert [node.name for node in breadcrumb] == ["Rome", "Forum"]


@allure.story(_STORY_BUILDER)
@allure.title("build_world_view guards the breadcrumb against a cyclic parent chain")
def test_builder_breadcrumb_handles_cycle(game_state: GameState) -> None:
    here = _place(game_state, "Forum", location_type="district")
    other = _place(game_state, "Loop", location_type="district", parent_location_id=here.uuid)
    here.parent_location_id = other.uuid  # here -> other -> here ...
    game_state.player.location_id = here.uuid

    breadcrumb = build_world_view(game_state).map.breadcrumb

    # The visited-set guard stops the walk; it never loops forever.
    assert [node.name for node in breadcrumb] == ["Loop"]


@allure.story(_STORY_BUILDER)
@allure.title("build_world_view name-gates present NPCs through label_for_player")
def test_builder_people_name_gated(game_state: GameState) -> None:
    introduced = NPCCard(name="Marcus", occupation="legionary", short_descriptor="a stern soldier")
    stranger = NPCCard(name="Lucia", occupation="merchant", short_descriptor="a hooded merchant")
    game_state.npcs[introduced.uuid] = introduced
    game_state.npcs[stranger.uuid] = stranger
    game_state.player.known_npcs.add(introduced.uuid)
    _scene_with(
        game_state,
        make_uuid("scene-loc"),
        [SceneNPC(role="guard", uuid=introduced.uuid), SceneNPC(role="trader", uuid=stranger.uuid)],
    )

    people = build_world_view(game_state).people

    by_role = {person.role: person for person in people}
    assert by_role["guard"].label == "Marcus (legionary)"
    assert by_role["guard"].known is True
    assert by_role["trader"].label == "a hooded merchant"
    assert by_role["trader"].known is False


@allure.story(_STORY_BUILDER)
@allure.title("build_world_view falls back to the scene role when a SceneNPC has no card")
def test_builder_people_role_fallback(game_state: GameState) -> None:
    _scene_with(game_state, make_uuid("scene-loc"), [SceneNPC(role="beggar", uuid=None)])

    people = build_world_view(game_state).people

    assert len(people) == 1
    assert people[0].label == "beggar"
    assert people[0].role == "beggar"
    assert people[0].known is False


@allure.story(_STORY_BUILDER)
@allure.title("build_world_view returns no people when there is no current scene")
def test_builder_people_empty_without_scene(game_state: GameState) -> None:
    assert build_world_view(game_state).people == []


@allure.story(_STORY_BUILDER)
@allure.title("build_world_view derives day, hour, and a known time-of-day label from the clock")
def test_builder_clock_derivation(game_state: GameState) -> None:
    game_state.advance_clock(30.0)  # 30h -> day 2, hour 6, morning

    clock = build_world_view(game_state).clock

    assert clock.day == 2
    assert clock.hour == 6
    assert clock.time_of_day == "morning"
    assert clock.time_of_day in _KNOWN_TIME_LABELS


@allure.story(_STORY_BUILDER)
@allure.title("build_world_view returns an empty world for a fresh GameState")
def test_builder_handles_empty_state(game_state: GameState) -> None:
    world = build_world_view(game_state)

    assert world.map.current is None
    assert world.people == []
    assert world.clock.day == 1
    assert world.clock.time_of_day in _KNOWN_TIME_LABELS
