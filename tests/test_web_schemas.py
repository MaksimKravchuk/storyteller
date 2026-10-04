"""Shape tests for the ``CharacterInfo`` / ``KnownNPC`` / ``RememberedFact`` DTOs."""

from __future__ import annotations

import allure
import pytest
from pydantic import ValidationError

from interfaces.web.character_schemas import CharacterInfo, KnownNPC, RememberedFact
from interfaces.web.schemas import (
    ActionRequest,
    ActionResponse,
    CharacterCreationInput,
    GameSnapshot,
    PlayerGesture,
    StartGameRequest,
)
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
@allure.title("ActionResponse.action_html defaults to None and round-trips when set")
def test_action_response_action_html() -> None:
    without = ActionResponse(
        narration="", narration_html="", turn_count=1, character=_sample_character(), world=_sample_world()
    )
    assert without.action_html is None
    with_html = ActionResponse(
        narration="",
        narration_html="",
        action_html="talk to Marcus",
        turn_count=1,
        character=_sample_character(),
        world=_sample_world(),
    )
    assert with_html.action_html == "talk to Marcus"


@allure.story(_STORY_SCHEMA)
@allure.title("ActionRequest accepts a lone free-text action or a lone gesture")
def test_action_request_accepts_exactly_one() -> None:
    assert ActionRequest(action="look around").gesture is None
    gesture = PlayerGesture(intent="talk", entity_kind="npc", entity_id="npc-1")
    assert ActionRequest(gesture=gesture).action is None


@allure.story(_STORY_SCHEMA)
@allure.title("ActionRequest rejects both, neither, or a blank action")
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"action": "look", "gesture": {"intent": "talk", "entity_kind": "npc", "entity_id": "npc-1"}},
        {"action": "   "},
    ],
)
def test_action_request_xor(payload: dict) -> None:
    with pytest.raises(ValidationError):
        ActionRequest.model_validate(payload)


@allure.story(_STORY_SCHEMA)
@allure.title("PlayerGesture accepts every allowed intent×kind pair")
@pytest.mark.parametrize(
    ("intent", "entity_kind"),
    [
        ("examine", "npc"),
        ("examine", "poi"),
        ("examine", "item"),
        ("talk", "npc"),
        ("attack", "npc"),
        ("steal", "npc"),
        ("move", "location"),
    ],
)
def test_player_gesture_allows_valid_pairs(intent: str, entity_kind: str) -> None:
    gesture = PlayerGesture.model_validate({"intent": intent, "entity_kind": entity_kind, "entity_id": "e-1"})
    assert (gesture.intent, gesture.entity_kind) == (intent, entity_kind)


@allure.story(_STORY_SCHEMA)
@allure.title("PlayerGesture rejects mismatched intent×kind pairs and a blank entity_id")
@pytest.mark.parametrize(
    "payload",
    [
        {"intent": "talk", "entity_kind": "poi", "entity_id": "e-1"},
        {"intent": "move", "entity_kind": "npc", "entity_id": "e-1"},
        {"intent": "attack", "entity_kind": "poi", "entity_id": "e-1"},
        {"intent": "steal", "entity_kind": "item", "entity_id": "e-1"},
        {"intent": "examine", "entity_kind": "location", "entity_id": "e-1"},
        {"intent": "talk", "entity_kind": "npc", "entity_id": ""},
    ],
)
def test_player_gesture_rejects_invalid(payload: dict) -> None:
    with pytest.raises(ValidationError):
        PlayerGesture.model_validate(payload)


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
