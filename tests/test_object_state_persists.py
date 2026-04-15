"""KER-16 — persistent ``Location.object_states`` across scene rebuilds.

``SceneBuilder`` regenerates each scene from scratch, so without a
typed channel for mutable object state, LLM-produced
``points_of_interest`` would silently drop the "broken shutter" on
every turn. These tests pin the two protections that keep damage
visible end-to-end:

1. ``SceneBuilder.act`` injects the current location's
   ``object_states`` into the system prompt AND merges any entry the
   LLM omits from its response back into ``Scene.points_of_interest``.
2. ``Narrator._build_raw_parts`` appends a ``Prior damage:`` line on
   CONTINUATION turns so the lossy scene-history summary is not the
   only source of truth for what got broken earlier.
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
from models.scene import Scene

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


def _make_narrator() -> Narrator:
    llm_client = AsyncMock()
    llm_client.send_message = AsyncMock(
        return_value=AsyncMock(
            body="Narrated text.",
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        ),
    )
    return Narrator(llm_client=llm_client, language="English")


def _last_user_message(narrator: Narrator) -> str:
    call_kwargs = narrator.llm_client.send_message.call_args.kwargs  # type: ignore[attr-defined]
    return call_kwargs[_MESSAGES][-1].body


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

        merged = " ".join(scene.points_of_interest)
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
    @allure.title("SceneBuilder does not duplicate an object state entry the LLM already mentions in description")
    @pytest.mark.asyncio
    async def test_no_duplicate_when_already_mentioned(self, game_state) -> None:
        _seed_damaged_location(game_state)
        builder = SceneBuilder(llm_client=MagicMock())
        aware_payload = SceneResponse(
            location_id=_LOCATION_ID,
            description="The splintered shutter still hangs askew.",
            points_of_interest=["oak bar"],
        )
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=aware_payload)):
            scene = await builder.act("look around", {_GAME_STATE: game_state})

        synthesized_markers = [poi for poi in scene.points_of_interest if poi.startswith(_DAMAGE_KEY)]
        assert not synthesized_markers


@allure.epic("Narrative Delivery")
@allure.feature("Narrator")
class TestNarratorSurfacesPriorDamage:
    @allure.story("Object state persistence")
    @allure.title("Narrator emits a Prior damage line on CONTINUATION turns when object_states is non-empty")
    @pytest.mark.asyncio
    async def test_continuation_includes_prior_damage(self, game_state) -> None:
        _seed_damaged_location(game_state)
        narrator = _make_narrator()

        await narrator.act(
            input_data=TurnOutputs(),
            context={_PLAYER_ACTION: "look around", _GAME_STATE: game_state},
        )

        user_msg = _last_user_message(narrator)
        assert "Prior damage:" in user_msg
        assert _DAMAGE_KEY in user_msg
        assert "splintered" in user_msg

    @allure.story("Object state persistence")
    @allure.title("Narrator omits the Prior damage line when the current location has no tracked object state")
    @pytest.mark.asyncio
    async def test_continuation_omits_prior_damage_when_clean(self, game_state) -> None:
        _seed_damaged_location(game_state)
        game_state.locations[_LOCATION_ID].object_states.clear()
        narrator = _make_narrator()

        await narrator.act(
            input_data=TurnOutputs(),
            context={_PLAYER_ACTION: "look around", _GAME_STATE: game_state},
        )

        user_msg = _last_user_message(narrator)
        assert "Prior damage:" not in user_msg

    @allure.story("Object state persistence")
    @allure.title("Narrator does not emit Prior damage on NEW_SCENE turns because SceneBuilder already merges damage")
    @pytest.mark.asyncio
    async def test_new_scene_has_no_prior_damage_duplication(self, game_state) -> None:
        _seed_damaged_location(game_state)
        narrator = _make_narrator()
        fresh_scene = Scene(
            location_id=_LOCATION_ID,
            description="A dim tavern.",
            points_of_interest=["shutter (splintered; frame torn loose)"],
        )

        await narrator.act(
            input_data=TurnOutputs(scene=fresh_scene),
            context={_PLAYER_ACTION: "enter", _GAME_STATE: game_state},
        )

        user_msg = _last_user_message(narrator)
        assert "Prior damage:" not in user_msg
