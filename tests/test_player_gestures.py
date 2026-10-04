"""Unit tests for ``interfaces.web.player_gestures.compose_player_gesture``.

Covers resolution of each entity kind against **persisted** current state,
name-gating through ``label_for_player``, EN/RU phrase composition, and the
error paths. Resolution must not depend on ``last_visible_entities`` (which
is empty after ``resume_session``), so every test leaves it at its empty
default.
"""

from __future__ import annotations

from uuid import UUID

import allure
import pytest

from interfaces.web.player_gestures import GestureResolutionError, compose_player_gesture
from interfaces.web.schemas import PlayerGesture
from models.game_state import GameState
from models.location import Location
from models.npc_card import NPCCard
from models.scene import PointOfInterest, Scene, SceneNPC
from tests._uuid_helpers import make_uuid

_STORY = "Player gesture composition"

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Web UI"),
]


def _place(game_state: GameState, name: str, **kwargs) -> Location:
    location = Location(name=name, location_type=kwargs.pop("location_type", "generic"), **kwargs)
    game_state.locations[location.uuid] = location
    return location


@allure.story(_STORY)
@allure.title("talk→npc resolves an introduced NPC to its gated label, composed per locale")
def test_npc_introduced(game_state: GameState) -> None:
    marcus = NPCCard(name="Marcus", occupation="legionary", short_descriptor="a stern soldier")
    game_state.npcs[marcus.uuid] = marcus
    game_state.player.known_npcs.add(marcus.uuid)
    game_state.current_scene = Scene(
        location_id=make_uuid("loc"), npcs_present=[SceneNPC(role="guard", uuid=marcus.uuid)]
    )

    gesture = PlayerGesture(intent="talk", entity_kind="npc", entity_id=str(marcus.uuid))
    assert compose_player_gesture(game_state, "English", gesture) == "talk to Marcus (legionary)"
    assert compose_player_gesture(game_state, "Russian", gesture) == "поговорить с Marcus (legionary)"


@allure.story(_STORY)
@allure.title("examine→npc on a stranger uses the descriptor, never a leaked name")
def test_npc_stranger_not_leaked(game_state: GameState) -> None:
    lucia = NPCCard(name="Lucia", occupation="merchant", short_descriptor="a hooded merchant")
    game_state.npcs[lucia.uuid] = lucia
    game_state.current_scene = Scene(
        location_id=make_uuid("loc"), npcs_present=[SceneNPC(role="trader", uuid=lucia.uuid)]
    )

    gesture = PlayerGesture(intent="examine", entity_kind="npc", entity_id=str(lucia.uuid))
    phrase = compose_player_gesture(game_state, "English", gesture)
    assert phrase == "examine a hooded merchant"
    assert "Lucia" not in phrase


@allure.story(_STORY)
@allure.title("npc with no generated card falls back to the scene role")
def test_npc_card_missing_uses_role(game_state: GameState) -> None:
    uuid = make_uuid("ghost-npc")
    game_state.current_scene = Scene(location_id=make_uuid("loc"), npcs_present=[SceneNPC(role="beggar", uuid=uuid)])
    gesture = PlayerGesture(intent="talk", entity_kind="npc", entity_id=str(uuid))
    assert compose_player_gesture(game_state, "English", gesture) == "talk to beggar"


@allure.story(_STORY)
@allure.title("attack/steal→npc compose in the session language with the gated label")
@pytest.mark.parametrize(
    ("intent", "language", "expected"),
    [
        ("attack", "English", "attack a hooded merchant"),
        ("steal", "English", "steal from a hooded merchant"),
        ("attack", "Russian", "напасть на a hooded merchant"),
        ("steal", "Russian", "обокрасть a hooded merchant"),
    ],
)
def test_npc_hostile_intents(game_state: GameState, intent: str, language: str, expected: str) -> None:
    lucia = NPCCard(name="Lucia", occupation="merchant", short_descriptor="a hooded merchant")
    game_state.npcs[lucia.uuid] = lucia
    game_state.current_scene = Scene(
        location_id=make_uuid("loc"), npcs_present=[SceneNPC(role="trader", uuid=lucia.uuid)]
    )
    gesture = PlayerGesture.model_validate({"intent": intent, "entity_kind": "npc", "entity_id": str(lucia.uuid)})
    assert compose_player_gesture(game_state, language, gesture) == expected


@allure.story(_STORY)
@allure.title("examine→poi resolves a point of interest to its primary name")
def test_poi(game_state: GameState) -> None:
    poi = PointOfInterest(names=["the marble fountain", "fountain"])
    game_state.current_scene = Scene(location_id=make_uuid("loc"), points_of_interest=[poi])
    gesture = PlayerGesture(intent="examine", entity_kind="poi", entity_id=str(poi.uuid))
    assert compose_player_gesture(game_state, "English", gesture) == "examine the marble fountain"


@allure.story(_STORY)
@allure.title("examine→item resolves a tracked object_states key at the scene location")
def test_item(game_state: GameState) -> None:
    location = _place(game_state, "Cell", object_states={"bronze key": "on the floor"})
    game_state.current_scene = Scene(location_id=location.uuid)
    gesture = PlayerGesture(intent="examine", entity_kind="item", entity_id="bronze key")
    assert compose_player_gesture(game_state, "Russian", gesture) == "осмотреть bronze key"


@allure.story(_STORY)
@allure.title("move→location resolves a reachable map node to its name")
def test_location_reachable(game_state: GameState) -> None:
    tavern = _place(game_state, "The Tavern", location_type="building")
    here = _place(game_state, "Forum", location_type="district", connected_locations=[tavern.uuid])
    game_state.player.location_id = here.uuid

    gesture = PlayerGesture(intent="move", entity_kind="location", entity_id=str(tavern.uuid))
    assert compose_player_gesture(game_state, "English", gesture) == "go to The Tavern"


@allure.story(_STORY)
@allure.title("resolution ignores last_visible_entities (empty after resume)")
def test_independent_of_last_visible_entities(game_state: GameState) -> None:
    poi = PointOfInterest(names=["a brass door"])
    game_state.current_scene = Scene(location_id=make_uuid("loc"), points_of_interest=[poi])
    game_state.last_visible_entities = []  # the post-resume reality
    gesture = PlayerGesture(intent="examine", entity_kind="poi", entity_id=str(poi.uuid))
    assert compose_player_gesture(game_state, "English", gesture) == "examine a brass door"


@allure.story(_STORY)
@allure.title("a missing scene raises GestureResolutionError")
def test_no_scene_raises(game_state: GameState) -> None:
    gesture = PlayerGesture(intent="examine", entity_kind="poi", entity_id="poi-1")
    with pytest.raises(GestureResolutionError):
        compose_player_gesture(game_state, "English", gesture)


@allure.story(_STORY)
@allure.title("stale or not-currently-visible ids raise GestureResolutionError")
@pytest.mark.parametrize(
    ("intent", "entity_kind", "entity_id"),
    [
        ("talk", "npc", "11111111-1111-1111-1111-111111111111"),
        ("examine", "poi", "22222222-2222-2222-2222-222222222222"),
        ("examine", "item", "no such key"),
        ("move", "location", "33333333-3333-3333-3333-333333333333"),
    ],
)
def test_unknown_ids_raise(game_state: GameState, intent: str, entity_kind: str, entity_id: str) -> None:
    here = _place(game_state, "Forum", object_states={"a torch": "lit"})
    game_state.player.location_id = here.uuid
    game_state.current_scene = Scene(location_id=here.uuid)
    gesture = PlayerGesture.model_validate({"intent": intent, "entity_kind": entity_kind, "entity_id": entity_id})
    with pytest.raises(GestureResolutionError):
        compose_player_gesture(game_state, "English", gesture)


@allure.story(_STORY)
@allure.title("a SceneNPC stub with no uuid is skipped during npc resolution")
def test_npc_uuid_none_skipped(game_state: GameState) -> None:
    real = NPCCard(name="Quintus", occupation="smith")
    game_state.npcs[real.uuid] = real
    game_state.player.known_npcs.add(real.uuid)
    game_state.current_scene = Scene(
        location_id=make_uuid("loc"),
        npcs_present=[SceneNPC(role="bystander", uuid=None), SceneNPC(role="smith", uuid=real.uuid)],
    )
    # Target the real NPC; the uuid-less stub must not shadow or crash resolution.
    gesture = PlayerGesture(intent="talk", entity_kind="npc", entity_id=str(real.uuid))
    assert compose_player_gesture(game_state, "English", gesture) == "talk to Quintus (smith)"


@allure.story(_STORY)
@allure.title("entity_id types match the ids the server emits for inline spans (str of uuid)")
def test_entity_id_is_str_uuid(game_state: GameState) -> None:
    poi = PointOfInterest(names=["an altar"])
    game_state.current_scene = Scene(location_id=make_uuid("loc"), points_of_interest=[poi])
    assert isinstance(poi.uuid, UUID)
    gesture = PlayerGesture(intent="examine", entity_kind="poi", entity_id=str(poi.uuid))
    assert compose_player_gesture(game_state, "English", gesture).endswith("an altar")
