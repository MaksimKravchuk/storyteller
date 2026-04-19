"""KER-16 — persistent ``Location.object_states`` across scene rebuilds.

``SceneBuilder`` regenerates each scene from scratch, so without a
typed channel for mutable object state, LLM-produced
``points_of_interest`` would silently drop the "broken shutter" on
every turn. These tests pin the protections that keep damage visible
end-to-end:

1. ``SceneBuilder.act`` injects the current location's
   ``object_states`` into the system prompt AND merges any entry the
   LLM omits from its response back into ``Scene.points_of_interest``.
2. ``Narrator._build_raw_parts`` appends a ``Prior damage:`` line on
   CONTINUATION turns so the lossy scene-history summary is not the
   only source of truth for what got broken earlier.
3. The whole-word safety-net match in SceneBuilder does not false-match
   a short key inside an unrelated word.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from cast.narrator import Narrator
from cast.scene_builder import SceneBuilder
from cast.schemas.scene_response import SceneResponse
from cast.schemas.turn_outputs import TurnOutputs
from models.location import Location
from models.scene import PointOfInterest, Scene

_SEND_JSON = "_send_json"
_PLAYER_ACTION = "player_action"
_GAME_STATE = "game_state"
_MESSAGES = "messages"
_DAMAGE_KEY = "shutter"
_DAMAGE_STATE = "splintered; frame torn loose"
_LOCATION_ID = "tavern"


def _seed_damaged_location(game_state) -> None:
    """Attach a tavern with a splintered shutter to the shared game_state fixture."""
    location = Location(
        uuid=_LOCATION_ID,
        name="Tavern",
        description="A dim tavern.",
        object_states={_DAMAGE_KEY: _DAMAGE_STATE},
    )
    game_state.locations[_LOCATION_ID] = location
    game_state.player.location_id = _LOCATION_ID
    game_state.current_scene = Scene(location_id=_LOCATION_ID, description="A dim tavern.")


def _make_narrator() -> tuple[Narrator, AsyncMock]:
    """Build a Narrator with a stubbed ``send_message`` for prompt inspection.

    Returns the narrator and the ``send_message`` mock so tests can read
    ``mock.call_args`` without poking at the typed ``llm_client`` attribute
    (which would trip mypy's ``attr-defined`` check).
    """
    mock_send = AsyncMock(
        return_value=AsyncMock(
            body="Narrated text.",
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        ),
    )
    llm_client = AsyncMock()
    llm_client.send_message = mock_send
    narrator = Narrator(llm_client=llm_client, language="English")
    return narrator, mock_send


def _last_user_message(mock_send: AsyncMock) -> str:
    messages = mock_send.call_args.kwargs[_MESSAGES]
    return messages[-1].body


@allure.epic("Scene & Exploration")
@allure.feature("Scene Builder")
class TestSceneBuilderPreservesObjectStates:
    @allure.story("Object state persistence")
    @allure.title("SceneBuilder injects known_object_states into the system prompt before calling the LLM")
    @pytest.mark.asyncio
    async def test_system_prompt_carries_known_object_states(self, game_state) -> None:
        _seed_damaged_location(game_state)
        builder = SceneBuilder(llm_client=MagicMock())
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=SceneResponse())):
            await builder.act("look around", {_GAME_STATE: game_state})

        rendered_system = builder._build_system_prompt()
        assert "Known object states" in rendered_system
        assert _DAMAGE_KEY in rendered_system
        assert "splintered" in rendered_system

    @allure.story("Object state persistence")
    @allure.title("SceneBuilder re-injects dropped object states into Scene.points_of_interest after the LLM response")
    @pytest.mark.asyncio
    async def test_merge_back_missing_object_state(self, game_state) -> None:
        _seed_damaged_location(game_state)
        builder = SceneBuilder(llm_client=MagicMock())
        pristine_payload = SceneResponse(
            location_id=_LOCATION_ID,
            description="A pristine tavern with no damage visible.",
            points_of_interest=["oak bar"],
        )
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=pristine_payload)):
            scene = await builder.act("look around", {_GAME_STATE: game_state})

        merged = " ".join(poi.primary_name for poi in scene.points_of_interest)
        assert _DAMAGE_KEY in merged
        assert "splintered" in merged

    @allure.story("Object state persistence")
    @allure.title("SceneBuilder leaves Location.object_states untouched after a rebuild so state is not reset")
    @pytest.mark.asyncio
    async def test_object_states_not_mutated_by_rebuild(self, game_state) -> None:
        _seed_damaged_location(game_state)
        builder = SceneBuilder(llm_client=MagicMock())
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=SceneResponse())):
            await builder.act("look around", {_GAME_STATE: game_state})

        assert game_state.locations[_LOCATION_ID].object_states == {_DAMAGE_KEY: _DAMAGE_STATE}

    @allure.story("Object state persistence")
    @allure.title("SceneBuilder omits the known_object_states section when the current location has no tracked state")
    @pytest.mark.asyncio
    async def test_section_omitted_when_no_states(self, game_state) -> None:
        _seed_damaged_location(game_state)
        game_state.locations[_LOCATION_ID].object_states.clear()
        builder = SceneBuilder(llm_client=MagicMock())
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=SceneResponse())):
            await builder.act("look around", {_GAME_STATE: game_state})

        rendered_system = builder._build_system_prompt()
        assert "Known object states" not in rendered_system

    @allure.story("Object state persistence")
    @allure.title("SceneBuilder does not duplicate an object state entry the LLM already mentions in the description")
    @pytest.mark.asyncio
    async def test_no_duplicate_when_mentioned_in_description(self, game_state) -> None:
        _seed_damaged_location(game_state)
        builder = SceneBuilder(llm_client=MagicMock())
        aware_payload = SceneResponse(
            location_id=_LOCATION_ID,
            description="The splintered shutter still hangs askew.",
            points_of_interest=["oak bar"],
        )
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=aware_payload)):
            scene = await builder.act("look around", {_GAME_STATE: game_state})

        synthesized_markers = [poi for poi in scene.points_of_interest if poi.primary_name.startswith(_DAMAGE_KEY)]
        assert not synthesized_markers

    @allure.story("Object state persistence")
    @allure.title("SceneBuilder does not duplicate an entry the LLM already mentions in a point of interest")
    @pytest.mark.asyncio
    async def test_no_duplicate_when_mentioned_in_points_of_interest(self, game_state) -> None:
        _seed_damaged_location(game_state)
        builder = SceneBuilder(llm_client=MagicMock())
        poi_payload = SceneResponse(
            location_id=_LOCATION_ID,
            description="A pristine tavern.",
            points_of_interest=["Broken Shutter hanging on its hinges"],
        )
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=poi_payload)):
            scene = await builder.act("look around", {_GAME_STATE: game_state})

        synthesized_markers = [
            poi for poi in scene.points_of_interest if poi.primary_name.lower().startswith(_DAMAGE_KEY)
        ]
        assert not synthesized_markers

    @allure.story("Object state persistence")
    @allure.title("SceneBuilder safety net fires when a short object_key only appears as a substring of another word")
    @pytest.mark.asyncio
    async def test_safety_net_fires_on_word_fragment_collision(self, game_state) -> None:
        _seed_damaged_location(game_state)
        game_state.locations[_LOCATION_ID].object_states = {"bar": "cracked down the middle"}
        builder = SceneBuilder(llm_client=MagicMock())
        fragment_payload = SceneResponse(
            location_id=_LOCATION_ID,
            description="A tavern behind a wooden barricade.",
            points_of_interest=["barrel"],
        )
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=fragment_payload)):
            scene = await builder.act("look around", {_GAME_STATE: game_state})

        merged = " ".join(poi.primary_name for poi in scene.points_of_interest)
        assert "bar" in merged
        assert "cracked down the middle" in merged

    @allure.story("Object state persistence")
    @allure.title("SceneBuilder falls back to the current scene's location_id when the player has not been placed")
    @pytest.mark.asyncio
    async def test_scene_fallback_when_player_location_unset(self, game_state) -> None:
        _seed_damaged_location(game_state)
        game_state.player.location_id = None
        builder = SceneBuilder(llm_client=MagicMock())
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=SceneResponse())):
            await builder.act("look around", {_GAME_STATE: game_state})

        rendered_system = builder._build_system_prompt()
        assert "Known object states" in rendered_system
        assert _DAMAGE_KEY in rendered_system

    @allure.story("Object state persistence")
    @allure.title("SceneBuilder renders multi-entry object_states in sorted key order")
    @pytest.mark.asyncio
    async def test_multi_entry_sort_order(self, game_state) -> None:
        _seed_damaged_location(game_state)
        game_state.locations[_LOCATION_ID].object_states = {
            "zebra pelt": "faded",
            "anvil": "chipped",
        }
        builder = SceneBuilder(llm_client=MagicMock())
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=SceneResponse())):
            await builder.act("look around", {_GAME_STATE: game_state})

        rendered_system = builder._build_system_prompt()
        anvil_pos = rendered_system.find("anvil")
        zebra_pos = rendered_system.find("zebra pelt")
        assert anvil_pos != -1 and zebra_pos != -1
        assert anvil_pos < zebra_pos


@allure.epic("Narrative Delivery")
@allure.feature("Narrator")
class TestNarratorSurfacesPriorDamage:
    @allure.story("Object state persistence")
    @allure.title("Narrator emits a Prior damage line on CONTINUATION turns when object_states is non-empty")
    @pytest.mark.asyncio
    async def test_continuation_includes_prior_damage(self, game_state) -> None:
        _seed_damaged_location(game_state)
        narrator, mock_send = _make_narrator()

        await narrator.act(
            input_data=TurnOutputs(),
            context={_PLAYER_ACTION: "look around", _GAME_STATE: game_state},
        )

        user_msg = _last_user_message(mock_send)
        expected_line = "Prior damage:\n- {0}: {1}".format(_DAMAGE_KEY, _DAMAGE_STATE)
        assert expected_line in user_msg

    @allure.story("Object state persistence")
    @allure.title("Narrator omits the Prior damage line when the current location has no tracked object state")
    @pytest.mark.asyncio
    async def test_continuation_omits_prior_damage_when_clean(self, game_state) -> None:
        _seed_damaged_location(game_state)
        game_state.locations[_LOCATION_ID].object_states.clear()
        narrator, mock_send = _make_narrator()

        await narrator.act(
            input_data=TurnOutputs(),
            context={_PLAYER_ACTION: "look around", _GAME_STATE: game_state},
        )

        user_msg = _last_user_message(mock_send)
        assert "Prior damage:" not in user_msg

    @allure.story("Object state persistence")
    @allure.title("Narrator omits the Prior damage line when the location cannot be resolved")
    @pytest.mark.asyncio
    async def test_continuation_omits_prior_damage_when_location_missing(self, game_state) -> None:
        _seed_damaged_location(game_state)
        game_state.player.location_id = "ghost"
        game_state.current_scene = Scene(location_id="ghost", description="Nowhere.")
        narrator, mock_send = _make_narrator()

        await narrator.act(
            input_data=TurnOutputs(),
            context={_PLAYER_ACTION: "look around", _GAME_STATE: game_state},
        )

        user_msg = _last_user_message(mock_send)
        assert "Prior damage:" not in user_msg

    @allure.story("Object state persistence")
    @allure.title("Narrator does not emit Prior damage when a scene is supplied on the current turn")
    @pytest.mark.asyncio
    async def test_new_scene_has_no_prior_damage_duplication(self, game_state) -> None:
        _seed_damaged_location(game_state)
        narrator, mock_send = _make_narrator()
        fresh_scene = Scene(
            location_id=_LOCATION_ID,
            description="A dim tavern.",
            points_of_interest=[PointOfInterest(names=["shutter (splintered; frame torn loose)"])],
        )

        await narrator.act(
            input_data=TurnOutputs(scene=fresh_scene),
            context={_PLAYER_ACTION: "enter", _GAME_STATE: game_state},
        )

        user_msg = _last_user_message(mock_send)
        assert "Prior damage:" not in user_msg

    @allure.story("Object state persistence")
    @allure.title("Narrator renders multi-entry prior damage in sorted key order")
    @pytest.mark.asyncio
    async def test_multi_entry_prior_damage_is_sorted(self, game_state) -> None:
        _seed_damaged_location(game_state)
        game_state.locations[_LOCATION_ID].object_states = {
            "zebra pelt": "faded",
            "anvil": "chipped",
        }
        narrator, mock_send = _make_narrator()

        await narrator.act(
            input_data=TurnOutputs(),
            context={_PLAYER_ACTION: "look around", _GAME_STATE: game_state},
        )

        user_msg = _last_user_message(mock_send)
        anvil_pos = user_msg.find("anvil")
        zebra_pos = user_msg.find("zebra pelt")
        assert anvil_pos != -1 and zebra_pos != -1
        assert anvil_pos < zebra_pos
