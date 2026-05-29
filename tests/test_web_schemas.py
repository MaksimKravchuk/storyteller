"""Shape tests for the ``CharacterInfo`` / ``KnownNPC`` / ``RememberedFact`` DTOs."""

from __future__ import annotations

import allure
import pytest
from pydantic import ValidationError

from interfaces.web.character_schemas import CharacterInfo, KnownNPC, RememberedFact
from interfaces.web.schemas import ActionResponse, CharacterCreationInput, GameSnapshot, StartGameRequest
from interfaces.web.world_schemas import LocationNode, MapView, ScenePerson, WorldClock, WorldView

_STORY_SCHEMA = "Character info schema"
_STORY_WORLD_SCHEMA = "World view schema"

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Web UI"),
]


def _sample_character() -> CharacterInfo:
    return CharacterInfo(
        name="Aurelia",
        appearance="A weathered traveller.",
        physical_status="healthy",
        inventory=["waterskin"],
        known_npcs=[KnownNPC(name="Marcus", occupation="legionary", descriptor="a stern soldier")],
        recent_events=["Met Marcus"],
        learned_facts=[RememberedFact(text="The forum is crowded.", source="PERSONAL_EXPERIENCE")],
    )


def _sample_world() -> WorldView:
    return WorldView(
        map=MapView(
            current=LocationNode(id="loc-forum", name="Forum Romanum", location_type="district"),
            connections=[LocationNode(id="loc-tavern", name="The Tavern", location_type="building")],
            breadcrumb=[LocationNode(id="loc-rome", name="Rome", location_type="city")],
        ),
        people=[ScenePerson(label="a stern guard", role="guard", known=False)],
        clock=WorldClock(day=2, time_of_day="afternoon", hour=14),
    )


@allure.story(_STORY_SCHEMA)
@allure.title("CharacterInfo serialises every field through pydantic")
def test_character_info_round_trip() -> None:
    character = _sample_character()
    dumped = character.model_dump()

    assert dumped["name"] == "Aurelia"
    assert dumped["inventory"] == ["waterskin"]
    assert dumped["recent_events"] == ["Met Marcus"]
    assert dumped["known_npcs"][0]["descriptor"] == "a stern soldier"
    assert dumped["learned_facts"][0]["source"] == "PERSONAL_EXPERIENCE"


@allure.story(_STORY_SCHEMA)
@allure.title("CharacterInfo requires every field — partial construction raises ValidationError")
def test_character_info_requires_every_field() -> None:
    with pytest.raises(ValidationError):
        CharacterInfo(name="Aurelia")  # type: ignore[call-arg]


@allure.story(_STORY_SCHEMA)
@allure.title("GameSnapshot exposes a CharacterInfo under the ``character`` field")
def test_snapshot_exposes_character() -> None:
    character = _sample_character()
    snapshot = GameSnapshot(
        game_id="g-1",
        setting="Rome",
        transcript=[],
        turn_count=0,
        character=character,
        world=_sample_world(),
    )
    assert snapshot.character == character


@allure.story(_STORY_SCHEMA)
@allure.title("ActionResponse exposes a CharacterInfo under the ``character`` field")
def test_action_response_exposes_character() -> None:
    character = _sample_character()
    response = ActionResponse(
        narration="",
        narration_html="",
        turn_count=1,
        character=character,
        world=_sample_world(),
    )
    assert response.character == character


@allure.story(_STORY_SCHEMA)
@allure.title("KnownNPC and RememberedFact reject missing required fields")
def test_nested_models_require_fields() -> None:
    with pytest.raises(ValidationError):
        KnownNPC(name="Marcus")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        RememberedFact(text="a fact")  # type: ignore[call-arg]


@allure.story(_STORY_SCHEMA)
@allure.title("RememberedFact rejects a source string outside the FactSource Literal")
def test_remembered_fact_rejects_unknown_source() -> None:
    with pytest.raises(ValidationError):
        RememberedFact(text="a fact", source="NOT_A_SOURCE")  # type: ignore[arg-type]


_STORY_CHARACTER_INPUT = "Character creation input"


@allure.story(_STORY_CHARACTER_INPUT)
@allure.title("CharacterCreationInput accepts a fully-empty payload (anonymous start)")
def test_character_input_accepts_empty_payload() -> None:
    character = CharacterCreationInput()
    assert character.name == ""
    assert character.appearance == ""
    assert character.inventory == []


@allure.story(_STORY_CHARACTER_INPUT)
@allure.title("CharacterCreationInput trims whitespace and drops empty inventory items")
def test_character_input_strips_inventory() -> None:
    character = CharacterCreationInput(inventory=["  phone  ", "", "  ", "keys"])
    assert character.inventory == ["phone", "keys"]


@allure.story(_STORY_CHARACTER_INPUT)
@allure.title("CharacterCreationInput rejects an inventory item longer than the per-item cap")
def test_character_input_rejects_oversize_item() -> None:
    with pytest.raises(ValidationError):
        CharacterCreationInput(inventory=["x" * 65])


@allure.story(_STORY_CHARACTER_INPUT)
@allure.title("CharacterCreationInput rejects more than 20 inventory items")
def test_character_input_rejects_oversize_inventory_list() -> None:
    with pytest.raises(ValidationError):
        CharacterCreationInput(inventory=[f"item{idx}" for idx in range(21)])


@allure.story(_STORY_CHARACTER_INPUT)
@allure.title("CharacterCreationInput rejects an appearance longer than the cap")
def test_character_input_rejects_oversize_appearance() -> None:
    with pytest.raises(ValidationError):
        CharacterCreationInput(appearance="x" * 501)


@allure.story(_STORY_CHARACTER_INPUT)
@allure.title("StartGameRequest defaults character to None and accepts a nested payload")
def test_start_game_request_carries_character() -> None:
    bare = StartGameRequest(setting="Rome")
    assert bare.character is None

    populated = StartGameRequest(
        setting="Rome",
        character=CharacterCreationInput(name="Alex", appearance="grey hoodie"),
    )
    assert populated.character is not None
    assert populated.character.name == "Alex"


@allure.story(_STORY_WORLD_SCHEMA)
@allure.title("WorldView round-trips through model_validate(model_dump())")
def test_world_view_round_trip() -> None:
    world = _sample_world()

    restored = WorldView.model_validate(world.model_dump())

    assert restored == world
    dumped = world.model_dump()
    assert dumped["map"]["current"]["name"] == "Forum Romanum"
    assert dumped["map"]["connections"][0]["location_type"] == "building"
    assert dumped["people"][0]["known"] is False
    assert dumped["clock"] == {"day": 2, "time_of_day": "afternoon", "hour": 14}


@allure.story(_STORY_WORLD_SCHEMA)
@allure.title("MapView accepts a null current location")
def test_map_view_allows_null_current() -> None:
    map_view = MapView(current=None, connections=[], breadcrumb=[])
    assert map_view.current is None


@allure.story(_STORY_WORLD_SCHEMA)
@allure.title("GameSnapshot and ActionResponse expose a WorldView under the ``world`` field")
def test_responses_expose_world() -> None:
    world = _sample_world()
    snapshot = GameSnapshot(
        game_id="g-1",
        setting="Rome",
        transcript=[],
        turn_count=0,
        character=_sample_character(),
        world=world,
    )
    response = ActionResponse(
        narration="",
        narration_html="",
        turn_count=1,
        character=_sample_character(),
        world=world,
    )
    assert snapshot.world == world
    assert response.world == world


@allure.story(_STORY_WORLD_SCHEMA)
@allure.title("LocationNode and WorldClock reject missing required fields")
def test_world_nested_models_require_fields() -> None:
    with pytest.raises(ValidationError):
        LocationNode(id="loc-1", name="Forum")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        WorldClock(day=1, time_of_day="morning")  # type: ignore[call-arg]
