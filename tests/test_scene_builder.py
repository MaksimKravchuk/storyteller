"""Tests for cast.scene_builder.SceneBuilder — scene construction and context fallbacks."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from cast.scene_builder import SceneBuilder
from cast.schemas.scene_response import PointOfInterestResponse, SceneResponse
from models.scene import Scene, SceneNPC

_SEND_JSON = "_send_json"
_EXPECTED_SUMMARY_CAP = 500


def _full_scene_payload() -> SceneResponse:
    return SceneResponse(
        location_id="forum",
        description="A crowded plaza.",
        npcs_present=["senator", "merchant"],
        points_of_interest=["statue"],
        ambient_description="murmuring crowd",
        time_of_day="morning",
    )


@allure.epic("Scene & Exploration")
@allure.feature("Scene Builder")
class TestSceneBuilder:
    @allure.story("Scene construction")
    @allure.title("SceneBuilder converts a full LLM response into a Scene with typed SceneNPC entries")
    @pytest.mark.asyncio
    async def test_full_response_produces_scene(self, game_state) -> None:
        builder = SceneBuilder(llm_client=MagicMock())
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=_full_scene_payload())):
            scene = await builder.act("look around", {"game_state": game_state})
        assert isinstance(scene, Scene)
        assert scene.location_id == "forum"
        assert scene.description == "A crowded plaza."
        assert len(scene.npcs_present) == 2
        assert all(isinstance(npc, SceneNPC) for npc in scene.npcs_present)
        assert [npc.role for npc in scene.npcs_present] == ["senator", "merchant"]
        assert [poi.primary_name for poi in scene.points_of_interest] == ["statue"]
        assert scene.ambient_description == "murmuring crowd"
        assert scene.time_of_day == "morning"

    @allure.story("Scene construction")
    @allure.title("SceneBuilder accepts dict-form POIs so head-noun aliases flow through to PointOfInterest.names")
    @pytest.mark.asyncio
    async def test_poi_dict_form_preserves_head_aliases(self, game_state) -> None:
        builder = SceneBuilder(llm_client=MagicMock())
        payload = SceneResponse(
            points_of_interest=[
                PointOfInterestResponse(
                    names=["a wooden notice board with wax-sealed scrolls", "notice board", "board"],
                ),
                "a plain torch",
            ],
        )
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=payload)):
            scene = await builder.act("look", {"game_state": game_state})
        first, second = scene.points_of_interest
        assert first.names == ["a wooden notice board with wax-sealed scrolls", "notice board", "board"]
        assert first.primary_name == "a wooden notice board with wax-sealed scrolls"
        assert second.names == ["a plain torch"]

    @allure.story("Scene construction")
    @allure.title("SceneBuilder defaults every optional scene field when the LLM response is empty")
    @pytest.mark.asyncio
    async def test_empty_response_defaults(self, game_state) -> None:
        builder = SceneBuilder(llm_client=MagicMock())
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=SceneResponse())):
            scene = await builder.act("look", {"game_state": game_state})
        assert scene.location_id == "unknown"
        assert scene.description == ""
        assert scene.npcs_present == []
        assert scene.points_of_interest == []
        assert scene.ambient_description == ""
        assert scene.time_of_day == game_state.game_time

    @allure.story("Context truncation")
    @allure.title("SceneBuilder truncates the setting summary to 500 characters before injecting it into the prompt")
    @pytest.mark.asyncio
    async def test_setting_summary_truncation(self, game_state) -> None:
        game_state.setting.summary = "x" * 1200
        builder = SceneBuilder(llm_client=MagicMock())
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=SceneResponse())):
            await builder.act("look", {"game_state": game_state})
        injected = builder._system_prompt_vars["setting_summary"]
        assert len(injected) == _EXPECTED_SUMMARY_CAP

    @allure.story("Current location")
    @allure.title("SceneBuilder uses the 'Starting area' placeholder when no current scene is set on game state")
    @pytest.mark.asyncio
    async def test_starting_area_fallback(self, game_state) -> None:
        game_state.current_scene = None
        builder = SceneBuilder(llm_client=MagicMock())
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=SceneResponse())):
            await builder.act("look", {"game_state": game_state})
        assert builder._system_prompt_vars["current_location"] == "Starting area"

    @allure.story("Current location")
    @allure.title("SceneBuilder uses the current scene's description as the current_location context variable")
    @pytest.mark.asyncio
    async def test_uses_current_scene_description(self, game_state) -> None:
        game_state.current_scene = Scene(location_id="home", description="A warm hearth.")
        builder = SceneBuilder(llm_client=MagicMock())
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=SceneResponse())):
            await builder.act("look", {"game_state": game_state})
        assert builder._system_prompt_vars["current_location"] == "A warm hearth."

    @allure.story("NPC construction")
    @allure.title("SceneBuilder turns each npcs_present string into a SceneNPC whose uuid starts as None")
    @pytest.mark.asyncio
    async def test_npcs_present_uuid_none(self, game_state) -> None:
        builder = SceneBuilder(llm_client=MagicMock())
        payload = SceneResponse(npcs_present=["guard"])
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=payload)):
            scene = await builder.act("look", {"game_state": game_state})
        assert scene.npcs_present[0].uuid is None
        assert scene.npcs_present[0].role == "guard"

    @allure.story("Persistent world changes")
    @allure.title("SceneBuilder omits the persistent_world_changes section when no scene_state deltas exist")
    @pytest.mark.asyncio
    async def test_no_deltas_section_omitted(self, game_state) -> None:
        builder = SceneBuilder(llm_client=MagicMock())
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=SceneResponse())):
            await builder.act("look", {"game_state": game_state})
        rendered_system = builder.system_prompt_template.render(**builder._system_prompt_vars)
        assert "Persistent world changes" not in rendered_system

    @allure.story("Persistent world changes")
    @allure.title("SceneBuilder injects scene_state deltas grouped by location_id into the system prompt")
    @pytest.mark.asyncio
    async def test_deltas_injected_into_system_prompt(self, game_state) -> None:
        from knowledge.scene_state import record_scene_delta

        record_scene_delta(
            game_state.knowledge_graph,
            location_id="tavern",
            delta_text="The front window is broken.",
        )
        record_scene_delta(
            game_state.knowledge_graph,
            location_id="forum",
            delta_text="The statue of Jupiter is toppled.",
        )
        builder = SceneBuilder(llm_client=MagicMock())
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=SceneResponse())):
            await builder.act("look", {"game_state": game_state})

        rendered_system = builder.system_prompt_template.render(**builder._system_prompt_vars)
        assert "Persistent world changes" in rendered_system
        assert "tavern: The front window is broken." in rendered_system
        assert "forum: The statue of Jupiter is toppled." in rendered_system
