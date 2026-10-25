"""Unit tests for :mod:`cast.scene_place` — stable places and their residents."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import allure
import pytest

from cast import _place_residents as place_residents, scene_place
from cast._scene_location import UNKNOWN_SCENE_LOCATION
from models.location import Location
from tests.director_helpers import GameState, KnowledgeGraph, NPCCard, Scene, SceneNPC, make_setting, make_uuid

_LANDING = make_uuid("scene-place-landing")
_TOWN = make_uuid("scene-place-town")


def _state(game_time: str = "afternoon") -> GameState:
    gs = GameState(
        setting=make_setting(),
        knowledge_graph=KnowledgeGraph(),
    )
    gs.game_time = game_time
    gs.locations[_LANDING] = Location(uuid=_LANDING, name="Landing")
    gs.player.location_id = _LANDING
    return gs


def _resident(gs: GameState, name: str, occupation: str, location_id: UUID = _LANDING, **fields: Any) -> NPCCard:
    npc = NPCCard(name=name, occupation=occupation, location_id=location_id, **fields)
    npc.uuid = make_uuid("scene-place-{0}".format(name))
    gs.npcs[npc.uuid] = npc
    gs.locations[location_id].add_npc(npc.uuid)
    return npc


def _new_scene(**fields: Any) -> Scene:
    return Scene(location_id=UNKNOWN_SCENE_LOCATION, **fields)


@allure.epic("Scene & Exploration")
@allure.feature("Scene places")
class TestEnterScene:
    @allure.story("Known place")
    @allure.title("A scene at a known place moves the player there and links it to where they came from")
    def test_known_place_moves_player_and_links(self) -> None:
        gs = _state()
        hall = Location(name="Hall")
        gs.locations[hall.uuid] = hall
        scene = Scene(location_id=hall.uuid)

        scene_place.enter_scene(gs, scene, allow_new_place=True)

        assert gs.player.location_id == hall.uuid
        assert hall.uuid in gs.locations[_LANDING].connected_locations
        assert _LANDING in hall.connected_locations

    @allure.story("New place")
    @allure.title("Travelling to an unknown place registers a new Location named by the Scene Builder")
    def test_move_to_unknown_place_creates_location(self) -> None:
        gs = _state()
        scene = _new_scene(place_name="  Upper path ", description="A path. Snow everywhere.")

        scene_place.enter_scene(gs, scene, allow_new_place=True)

        new_place = gs.locations[scene.location_id]
        assert scene.location_id not in {_LANDING, UNKNOWN_SCENE_LOCATION}
        assert gs.player.location_id == scene.location_id
        assert new_place.name == "Upper path"
        assert new_place.description == "A path. Snow everywhere."

    @allure.story("New place")
    @allure.title("Without a name from the Scene Builder the new place is named after the description's first sentence")
    def test_new_place_falls_back_to_first_sentence(self) -> None:
        gs = _state()
        scene = _new_scene(description="A smoky forge. Sparks fly.")

        scene_place.enter_scene(gs, scene, allow_new_place=True)

        assert gs.locations[scene.location_id].name == "A smoky forge"

    @allure.story("New place")
    @allure.title("A new place with neither name nor description gets a placeholder name")
    def test_new_place_without_any_text_gets_placeholder(self) -> None:
        gs = _state()
        scene = _new_scene()

        scene_place.enter_scene(gs, scene, allow_new_place=True)

        assert gs.locations[scene.location_id].name == "Unnamed place"

    @allure.story("Staying put")
    @allure.title("A rebuild that does not travel (e.g. SLEEP) keeps the player's place when the id is unknown")
    def test_non_travel_rebuild_stays_at_current_place(self) -> None:
        gs = _state()
        scene = _new_scene(place_name="Somewhere else")

        scene_place.enter_scene(gs, scene, allow_new_place=False)

        assert scene.location_id == _LANDING
        assert gs.player.location_id == _LANDING
        assert set(gs.locations) == {_LANDING}
        assert gs.locations[_LANDING].connected_locations == []

    @allure.story("New place")
    @allure.title("A player with no place yet always gets a new Location, even on a non-travel rebuild")
    def test_player_without_place_gets_new_location(self) -> None:
        gs = _state()
        gs.player.location_id = None
        scene = _new_scene(place_name="Shore")

        scene_place.enter_scene(gs, scene, allow_new_place=False)

        assert gs.locations[scene.location_id].name == "Shore"
        assert gs.locations[scene.location_id].parent_location_id is None
        assert gs.locations[scene.location_id].connected_locations == []

    @allure.story("Hierarchy")
    @allure.title("A place reached from an area (city) sits inside it")
    def test_new_place_inside_coarse_origin(self) -> None:
        gs = _state()
        gs.locations[_TOWN] = Location(uuid=_TOWN, name="Town", location_type="city")
        gs.player.location_id = _TOWN
        scene = _new_scene(place_name="Market")

        scene_place.enter_scene(gs, scene, allow_new_place=True)

        assert gs.locations[scene.location_id].parent_location_id == _TOWN

    @allure.story("Hierarchy")
    @allure.title("A place reached from another spot sits beside it, under the same parent")
    def test_new_place_beside_fine_origin(self) -> None:
        gs = _state()
        gs.locations[_TOWN] = Location(uuid=_TOWN, name="Town", location_type="city")
        gs.locations[_LANDING].parent_location_id = _TOWN
        scene = _new_scene(place_name="Boathouse")

        scene_place.enter_scene(gs, scene, allow_new_place=True)

        assert gs.locations[scene.location_id].parent_location_id == _TOWN

    @allure.story("Hierarchy")
    @allure.title("Re-entering the same place does not link it to itself or duplicate links")
    def test_no_self_or_duplicate_links(self) -> None:
        gs = _state()
        hall = Location(name="Hall")
        gs.locations[hall.uuid] = hall

        scene_place.enter_scene(gs, Scene(location_id=_LANDING), allow_new_place=True)
        scene_place.enter_scene(gs, Scene(location_id=hall.uuid), allow_new_place=True)
        scene_place.enter_scene(gs, Scene(location_id=_LANDING), allow_new_place=True)
        scene_place.enter_scene(gs, Scene(location_id=hall.uuid), allow_new_place=True)

        assert gs.locations[_LANDING].connected_locations == [hall.uuid]
        assert hall.connected_locations == [_LANDING]


@allure.epic("Scene & Exploration")
@allure.feature("Scene places")
class TestSeatResidents:
    @allure.story("Residents")
    @allure.title("Residents who are there now are seated ahead of the Scene Builder's newcomers")
    def test_residents_seated_before_newcomers(self) -> None:
        gs = _state()
        eira = _resident(gs, "Eira", "net-mender")
        scene = Scene(location_id=_LANDING, npcs_present=[SceneNPC(role="old sailor")])

        scene_place.enter_scene(gs, scene, allow_new_place=True)

        assert [(snpc.role, snpc.uuid) for snpc in scene.npcs_present] == [
            ("net-mender", eira.uuid),
            ("old sailor", None),
        ]

    @allure.story("Residents")
    @allure.title("A newcomer role that re-describes a resident (by occupation word or name) is dropped")
    @pytest.mark.parametrize("role", ["net-mender woman", "woman mending nets, Eira"])
    def test_redescribed_resident_role_dropped(self, role: str) -> None:
        gs = _state()
        eira = _resident(gs, "Eira", "Fisher and net-mender")
        scene = Scene(location_id=_LANDING, npcs_present=[SceneNPC(role=role)])

        scene_place.enter_scene(gs, scene, allow_new_place=True)

        assert [snpc.uuid for snpc in scene.npcs_present] == [eira.uuid]

    @allure.story("Residents")
    @allure.title("A resident already in the scene is not seated twice and keeps its role")
    def test_already_seated_resident_not_duplicated(self) -> None:
        gs = _state()
        eira = _resident(gs, "Eira", "net-mender")
        scene = Scene(location_id=_LANDING, npcs_present=[SceneNPC(role="Eira", uuid=eira.uuid)])

        scene_place.enter_scene(gs, scene, allow_new_place=True)

        assert [(snpc.role, snpc.uuid) for snpc in scene.npcs_present] == [("Eira", eira.uuid)]

    @allure.story("Residents")
    @allure.title("A resident without an occupation is seated under their name")
    def test_resident_without_occupation_seated_by_name(self) -> None:
        gs = _state()
        _resident(gs, "Eira", "")
        scene = Scene(location_id=_LANDING)

        scene_place.enter_scene(gs, scene, allow_new_place=True)

        assert [snpc.role for snpc in scene.npcs_present] == ["Eira"]


@allure.epic("Scene & Exploration")
@allure.feature("Scene places")
class TestPresentResidents:
    @allure.story("Residents")
    @allure.title("Dead residents and residents whose schedule says they are away are not present")
    def test_dead_and_off_shift_residents_excluded(self) -> None:
        gs = _state(game_time="night")
        _resident(gs, "Ulf", "guard")
        _resident(gs, "Bodil", "net-mender", physical_status="dead")
        eira = _resident(gs, "Eira", "net-mender")

        assert place_residents.present_residents(gs, _LANDING) == [eira]

    @allure.story("Residents")
    @allure.title("People the player has met come first and the seated list is capped at five")
    def test_met_first_and_capped(self) -> None:
        gs = _state()
        strangers = [_resident(gs, "Stranger{0}".format(idx), "fisher") for idx in range(5)]
        introduced = _resident(gs, "Eira", "net-mender")
        talked_to = _resident(gs, "Ulf", "fisher", conversation_history=[{"player": "hi", "npc": "hello"}])
        gs.player.known_npcs.add(introduced.uuid)

        present = place_residents.present_residents(gs, _LANDING)

        assert present == [introduced, talked_to, *strangers[:3]]

    @allure.story("Residents")
    @allure.title("An unknown or missing location has no residents, and stale NPC ids are skipped")
    def test_unknown_location_and_stale_ids(self) -> None:
        gs = _state()
        gs.locations[_LANDING].add_npc(make_uuid("scene-place-ghost"))

        assert place_residents.present_residents(gs, None) == []
        assert place_residents.present_residents(gs, make_uuid("scene-place-nowhere")) == []
        assert place_residents.present_residents(gs, _LANDING) == []


@allure.epic("Scene & Exploration")
@allure.feature("Scene places")
class TestResidentNamed:
    @allure.story("Residents")
    @allure.title("A living resident is found by name case-insensitively, whatever their schedule says")
    def test_finds_resident_regardless_of_schedule(self) -> None:
        gs = _state(game_time="night")
        ulf = _resident(gs, "Ulf", "guard")

        assert place_residents.resident_named(gs, _LANDING, "  ulf ") is ulf

    @allure.story("Residents")
    @allure.title("Dead residents, other names and unknown places yield no one")
    def test_no_match_cases(self) -> None:
        gs = _state()
        _resident(gs, "Bodil", "net-mender", physical_status="dead")

        assert place_residents.resident_named(gs, _LANDING, "Bodil") is None
        assert place_residents.resident_named(gs, _LANDING, "Eira") is None
        assert place_residents.resident_named(gs, None, "Bodil") is None


@allure.epic("Scene & Exploration")
@allure.feature("Scene places")
class TestFormatKnownPlaces:
    @allure.story("Scene Builder prompt")
    @allure.title("Known places: short id, current place marked, present people named as the player knows them")
    def test_lines(self) -> None:
        gs = _state()
        hall = Location(name="Hall")
        gs.locations[hall.uuid] = hall
        _resident(gs, "Eira", "net-mender", short_descriptor="a woman mending nets")
        ulf = _resident(gs, "Ulf", "fisher")
        gs.player.known_npcs.add(ulf.uuid)

        text = scene_place.format_known_places(gs)

        landing_line = "- id {0}: Landing (the player is here now) | people here now: {1}".format(
            scene_place.place_key(_LANDING),
            "Ulf (fisher); a woman mending nets",
        )
        assert text.splitlines() == [landing_line, "- id {0}: Hall".format(scene_place.place_key(hall.uuid))]
        assert "Eira" not in text

    @allure.story("Scene Builder prompt")
    @allure.title("Only the most recent places are listed, but the player's current place always is")
    def test_cap_keeps_current_place(self) -> None:
        gs = _state()
        for idx in range(25):
            extra = Location(name="Place {0}".format(idx))
            gs.locations[extra.uuid] = extra

        lines = scene_place.format_known_places(gs).splitlines()

        assert len(lines) == 21
        assert lines[0].startswith("- id {0}: Landing".format(scene_place.place_key(_LANDING)))
        assert lines[1].endswith(": Place 5")
        assert lines[-1].endswith(": Place 24")

    @allure.story("Scene Builder prompt")
    @allure.title("No known places renders an empty string so the prompt section is dropped")
    def test_empty(self) -> None:
        gs = _state()
        gs.locations.clear()

        assert scene_place.format_known_places(gs) == ""


@allure.epic("Scene & Exploration")
@allure.feature("Scene places")
class TestAllTargetsInScene:
    @allure.story("Walking over vs travelling")
    @allure.title("Targets match scene NPCs by role, name or occupation; anyone absent means travel")
    def test_matching(self) -> None:
        gs = _state()
        eira = _resident(gs, "Eira", "net-mender")
        gs.current_scene = Scene(location_id=_LANDING, npcs_present=[SceneNPC(role="woman at the net", uuid=eira.uuid)])

        assert scene_place.all_targets_in_scene(["Woman at the net", "eira", "NET-MENDER"], gs)
        assert not scene_place.all_targets_in_scene(["Eira", "Ulf"], gs)

    @allure.story("Walking over vs travelling")
    @allure.title("Without a current scene nobody is here")
    def test_no_scene(self) -> None:
        gs = _state()

        assert not scene_place.all_targets_in_scene(["Eira"], gs)
