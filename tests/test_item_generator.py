"""Tests for cast.item_generator.ItemGenerator — batch expansion and single-item examination."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from cast.item_generator import ItemGenerator
from cast.schemas.item_response import ItemExamineResponse, ItemListResponse

_SEND_JSON = "_send_json"
_SETTING_CAP = 500


def _expanded_two() -> ItemListResponse:
    return ItemListResponse(items=["an iron sword with a leather grip", "a round wooden shield"])


@allure.epic("NPC Interaction")
@allure.feature("Item Generator")
class TestItemGenerator:
    @allure.story("Batch mode")
    @allure.title("ItemGenerator batch mode expands a list of item names into detailed descriptions")
    @pytest.mark.asyncio
    async def test_batch_expands_items(self, game_state) -> None:
        gen = ItemGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(return_value=_expanded_two())):
            expanded = await gen.act(
                ["sword", "shield"],
                {"game_state": game_state, "mode": "batch", "owner_context": "a grizzled veteran"},
            )
        assert expanded == _expanded_two().expanded

    @allure.story("Batch mode")
    @allure.title("ItemGenerator defaults to batch mode when the context does not include a mode key")
    @pytest.mark.asyncio
    async def test_default_mode_is_batch(self, game_state) -> None:
        gen = ItemGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(return_value=_expanded_two())):
            expanded = await gen.act(
                ["sword", "shield"],
                {"game_state": game_state, "owner_context": "ctx"},
            )
        assert expanded == _expanded_two().expanded

    @allure.story("Batch mode")
    @allure.title("ItemGenerator batch mode skips the LLM call entirely when the inventory is empty")
    @pytest.mark.asyncio
    async def test_empty_inventory_early_return(self, game_state) -> None:
        gen = ItemGenerator(llm_client=MagicMock())
        stub = AsyncMock(return_value=_expanded_two())
        with patch.object(gen, _SEND_JSON, new=stub):
            expanded = await gen.act([], {"game_state": game_state, "mode": "batch"})
        assert expanded == []
        assert stub.call_count == 0

    @allure.story("Batch mode")
    @allure.title("ItemGenerator batch mode returns the original inventory when the LLM returns the wrong item count")
    @pytest.mark.asyncio
    async def test_count_mismatch_fallback(self, game_state) -> None:
        gen = ItemGenerator(llm_client=MagicMock())
        payload = ItemListResponse(items=["only one"])
        with patch.object(gen, _SEND_JSON, new=AsyncMock(return_value=payload)):
            expanded = await gen.act(
                ["sword", "shield"],
                {"game_state": game_state, "mode": "batch"},
            )
        assert expanded == ["sword", "shield"]

    @allure.story("Batch mode")
    @allure.title("ItemGenerator batch mode falls back to the original inventory when the items key is missing")
    @pytest.mark.asyncio
    async def test_missing_items_key_fallback(self, game_state) -> None:
        gen = ItemGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(return_value=ItemListResponse())):
            expanded = await gen.act(
                ["sword", "shield"],
                {"game_state": game_state, "mode": "batch"},
            )
        assert expanded == ["sword", "shield"]

    @allure.story("Examine mode")
    @allure.title("ItemGenerator examine mode returns the description string from the LLM response")
    @pytest.mark.asyncio
    async def test_examine_returns_description(self, game_state) -> None:
        gen = ItemGenerator(llm_client=MagicMock())
        payload = ItemExamineResponse(description="a heavy iron key, rusted at the bow")
        with patch.object(gen, _SEND_JSON, new=AsyncMock(return_value=payload)):
            description = await gen.act(
                "key",
                {"game_state": game_state, "mode": "examine", "context_hint": "found in a chest"},
            )
        assert description == "a heavy iron key, rusted at the bow"

    @allure.story("Examine mode")
    @allure.title("ItemGenerator examine mode falls back to the item name when the description is missing")
    @pytest.mark.asyncio
    async def test_examine_missing_description_fallback(self, game_state) -> None:
        gen = ItemGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(return_value=ItemExamineResponse())):
            description = await gen.act(
                "torch",
                {"game_state": game_state, "mode": "examine"},
            )
        assert description == "torch"

    @allure.story("Context truncation")
    @allure.title("ItemGenerator truncates the setting summary to 500 characters before rendering the system prompt")
    @pytest.mark.asyncio
    async def test_setting_summary_truncation(self, game_state) -> None:
        game_state.setting.summary = "z" * 1200
        gen = ItemGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(return_value=_expanded_two())):
            await gen.act(
                ["sword", "shield"],
                {"game_state": game_state, "mode": "batch", "owner_context": "ctx"},
            )
        assert len(gen._system_prompt_vars["setting_summary"]) == _SETTING_CAP

    @allure.story("Batch mode")
    @allure.title("ItemGenerator batch prompt renders the inventory as a dash-prefixed bullet list in the prompt body")
    @pytest.mark.asyncio
    async def test_batch_bullet_list_in_prompt(self, game_state) -> None:
        gen = ItemGenerator(llm_client=MagicMock())
        stub = AsyncMock(return_value=_expanded_two())
        with patch.object(gen, _SEND_JSON, new=stub):
            await gen.act(
                ["sword", "shield"],
                {"game_state": game_state, "mode": "batch", "owner_context": "ctx"},
            )
        rendered_prompt = stub.call_args.args[0]
        assert "- sword\n- shield" in rendered_prompt
