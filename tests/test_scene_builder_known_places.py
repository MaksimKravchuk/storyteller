"""Scene Builder ↔ known places: the prompt lists them and a copied id resolves to the Location."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from cast._scene_location import UNKNOWN_SCENE_LOCATION
from cast.scene_builder import SceneBuilder
from cast.scene_place import place_key
from cast.schemas.scene_response import SceneResponse
from models.location import Location
from models.npc_card import NPCCard

_SEND_JSON = "_send_json"


@allure.epic("Scene & Exploration")
@allure.feature("Scene Builder")
class TestSceneBuilderKnownPlaces:
    @allure.story("Known places")
    @allure.title("A response naming a known place's short id lands the scene in that Location")
    @pytest.mark.asyncio
    async def test_known_place_id_resolves(self, game_state) -> None:
        landing = Location(name="Landing")
        game_state.locations[landing.uuid] = landing
        builder = SceneBuilder(llm_client=MagicMock())
        payload = SceneResponse(location_id=place_key(landing.uuid), location_name="the landing")
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=payload)):
            scene = await builder.act("walk back to the landing", {"game_state": game_state})
        assert scene.location_id == landing.uuid
        assert scene.place_name == "the landing"

    @allure.story("Known places")
    @allure.title("A response with a new snake_case id keeps the sentinel and carries the new place's name")
    @pytest.mark.asyncio
    async def test_new_place_keeps_sentinel_and_name(self, game_state) -> None:
        builder = SceneBuilder(llm_client=MagicMock())
        payload = SceneResponse(location_id="upper_village_path", location_name="Upper village path")
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=payload)):
            scene = await builder.act("walk up the path", {"game_state": game_state})
        assert scene.location_id == UNKNOWN_SCENE_LOCATION
        assert scene.place_name == "Upper village path"

    @allure.story("Known places")
    @allure.title("The system prompt lists known places with the people there now, in both locales")
    @pytest.mark.asyncio
    @pytest.mark.parametrize(("language", "header"), [("English", "Known places"), ("Russian", "Известные места")])
    async def test_known_places_reach_system_prompt(self, game_state, language: str, header: str) -> None:
        landing = Location(name="Landing")
        game_state.locations[landing.uuid] = landing
        game_state.player.location_id = landing.uuid
        eira = NPCCard(name="Eira", occupation="net-mender", location_id=landing.uuid)
        game_state.npcs[eira.uuid] = eira
        landing.add_npc(eira.uuid)
        game_state.player.known_npcs.add(eira.uuid)
        builder = SceneBuilder(llm_client=MagicMock(), language=language)
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=SceneResponse())):
            await builder.act("look", {"game_state": game_state})
        rendered = builder.system_prompt_template.render(**builder._system_prompt_vars)
        assert header in rendered
        assert "- id {0}: Landing (the player is here now)".format(place_key(landing.uuid)) in rendered
        assert "Eira (net-mender)" in rendered
