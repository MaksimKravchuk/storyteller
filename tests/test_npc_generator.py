"""Tests for cast.npc_generator.NPCGenerator — batch NPC card generation and context caps."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from cast.npc_generator import NPCGenerator
from cast.schemas.npc_response import NPCResponse
from models.npc_card import NPCCard
from models.scene import Scene

_SEND_JSON = "_send_json"
_SETTING_CAP = 500
_SCENE_CAP = 200
_SOCIAL_CAP = 300


def _full_npc_payload(name: str) -> NPCResponse:
    return NPCResponse(
        name=name,
        biography="{0} bio".format(name),
        appearance="tall",
        occupation="guard",
        personality_traits=["stern"],
        speech_style="gruff",
        knowledge_scope="city",
        attributes={"strength": 7},
        inventory=["sword"],
    )


@allure.epic("NPC Interaction")
@allure.feature("NPC Generator")
class TestNPCGenerator:
    @allure.story("Batch generation")
    @allure.title("NPCGenerator produces one NPCCard per requested role with all fields populated")
    @pytest.mark.asyncio
    async def test_one_card_per_request(self, game_state) -> None:
        gen = NPCGenerator(llm_client=MagicMock())
        payloads = [_full_npc_payload("Aulus"), _full_npc_payload("Brutus")]
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=payloads)):
            cards = await gen.act(["guard", "merchant"], {"game_state": game_state})
        assert len(cards) == 2
        assert all(isinstance(card, NPCCard) for card in cards)
        assert cards[0].name == "Aulus"
        assert cards[0].biography == "Aulus bio"
        assert cards[0].personality_traits == ["stern"]

    @allure.story("Batch generation")
    @allure.title("NPCGenerator defaults every missing LLM field including occupation from the request string")
    @pytest.mark.asyncio
    async def test_missing_fields_defaulted(self, game_state) -> None:
        gen = NPCGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[NPCResponse()])):
            cards = await gen.act(["tavern keeper"], {"game_state": game_state})
        card = cards[0]
        assert card.name == "Unknown"
        assert card.biography == ""
        assert card.occupation == "tavern keeper"
        assert card.personality_traits == []
        assert card.speech_style == "neutral"
        assert card.knowledge_scope == "local"
        assert card.attributes == {}
        assert card.inventory == []

    @allure.story("Location propagation")
    @allure.title("NPCGenerator stamps each card with the current scene's location_id from game state")
    @pytest.mark.asyncio
    async def test_location_propagation(self, game_state) -> None:
        game_state.current_scene = Scene(location_id="forum", description="plaza")
        gen = NPCGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[_full_npc_payload("Caius")])):
            cards = await gen.act(["guard"], {"game_state": game_state})
        assert cards[0].location_id == "forum"

    @allure.story("Location propagation")
    @allure.title("NPCGenerator leaves location_id None when the game state has no current scene")
    @pytest.mark.asyncio
    async def test_location_none_when_no_scene(self, game_state) -> None:
        game_state.current_scene = None
        gen = NPCGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[_full_npc_payload("Drusus")])):
            cards = await gen.act(["guard"], {"game_state": game_state})
        assert cards[0].location_id is None

    @allure.story("Batch generation")
    @allure.title("NPCGenerator preserves the input order when dispatching requests via asyncio.gather")
    @pytest.mark.asyncio
    async def test_gather_preserves_order(self, game_state) -> None:
        names = ["One", "Two", "Three", "Four", "Five"]
        payloads = [_full_npc_payload(n) for n in names]
        gen = NPCGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=payloads)):
            cards = await gen.act(names, {"game_state": game_state})
        assert [card.name for card in cards] == names

    @allure.story("Context truncation")
    @allure.title("NPCGenerator truncates setting summary, scene description, and social structure to their caps")
    @pytest.mark.asyncio
    async def test_context_truncation(self, game_state) -> None:
        game_state.setting.summary = "s" * 1200
        game_state.setting.social_structure = "h" * 1200
        game_state.current_scene = Scene(location_id="x", description="d" * 1200)
        gen = NPCGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[_full_npc_payload("X")])):
            await gen.act(["guard"], {"game_state": game_state})
        ctx = gen._system_prompt_vars
        assert len(ctx["setting_summary"]) == _SETTING_CAP
        assert len(ctx["location_name"]) == _SCENE_CAP
        assert len(ctx["social_structure"]) == _SOCIAL_CAP

    @allure.story("Context truncation")
    @allure.title("NPCGenerator labels the location as 'Unknown location' when no current scene is present")
    @pytest.mark.asyncio
    async def test_unknown_location_label(self, game_state) -> None:
        game_state.current_scene = None
        gen = NPCGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[_full_npc_payload("X")])):
            await gen.act(["guard"], {"game_state": game_state})
        assert gen._system_prompt_vars["location_name"] == "Unknown location"
