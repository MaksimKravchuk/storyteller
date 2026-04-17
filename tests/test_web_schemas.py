"""Shape tests for the ``CharacterInfo`` / ``KnownNPC`` / ``RememberedFact`` DTOs."""

from __future__ import annotations

import allure
import pytest
from pydantic import ValidationError

from interfaces.web.character_schemas import CharacterInfo, KnownNPC, RememberedFact
from interfaces.web.schemas import ActionResponse, GameSnapshot

_STORY_SCHEMA = "Character info schema"

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
