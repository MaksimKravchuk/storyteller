"""Tests for BasePerformer._send_json — JSON parsing, retries, and bracket extraction."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from cast.base_performer_class import BasePerformer
from prompts.base_template import PromptTemplate

_SEND_METHOD = "_send"
_PROMPT = "prompt"
_EMPTY_PROMPT = PromptTemplate([])


class _JsonPerformer(BasePerformer):
    async def act(self, input_data, context):
        return await self._send_json(input_data)


async def _bad_send(*args, **kwargs):
    raise UnicodeDecodeError("utf-8", b"", 0, 1, "reason")


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("BasePerformer JSON send")
class TestSendJson:
    @allure.story("Successful parse")
    @allure.title("BasePerformer._send_json parses a clean JSON response from the LLM into a dict")
    @pytest.mark.asyncio
    async def test_returns_dict_on_success(self):
        performer = self._make()
        with patch.object(performer, _SEND_METHOD, new=AsyncMock(return_value='{"key": "value"}')):
            output = await performer._send_json(_PROMPT)
        assert output == {"key": "value"}

    @allure.story("Bracket extraction")
    @allure.title(
        "BasePerformer._send_json recovers a JSON object embedded in surrounding prose via bracket extraction"
    )
    @pytest.mark.asyncio
    async def test_bracket_extraction_fallback(self):
        performer = self._make()
        with patch.object(performer, _SEND_METHOD, new=AsyncMock(return_value='noise {"extracted": true} noise')):
            extracted = await performer._send_json(_PROMPT, retries=0)
        assert extracted == {"extracted": True}

    @allure.story("Retry on bad JSON")
    @allure.title(
        "BasePerformer._send_json retries the requested number of times then raises when every attempt is invalid"
    )
    @pytest.mark.asyncio
    async def test_raises_when_all_retries_fail(self):
        performer = self._make()
        with patch.object(performer, _SEND_METHOD, new=AsyncMock(return_value="not json at all")) as mock_send:
            with pytest.raises(ValueError, match="failed to produce valid JSON"):
                await performer._send_json(_PROMPT, retries=2)
        assert mock_send.call_count == 3

    @allure.story("Bracket extraction")
    @allure.title(
        "BasePerformer._send_json raises a ValueError when the extracted brace region still contains broken JSON"
    )
    @pytest.mark.asyncio
    async def test_invalid_inner_braces(self):
        performer = self._make()
        with patch.object(performer, _SEND_METHOD, new=AsyncMock(return_value="prefix {broken json} suffix")):
            with pytest.raises(ValueError, match="failed to produce valid JSON"):
                await performer._send_json(_PROMPT, retries=0)

    @allure.story("Error handling")
    @allure.title(
        "Non-JSON exceptions raised by _send propagate out of _send_json instead of being swallowed as parse errors"
    )
    @pytest.mark.asyncio
    async def test_non_json_exception_propagates(self):
        performer = self._make()
        with patch.object(performer, _SEND_METHOD, new=_bad_send):
            with pytest.raises(UnicodeDecodeError):
                await performer._send_json(_PROMPT, retries=0)

    def _make(self) -> _JsonPerformer:
        return _JsonPerformer(llm_client=MagicMock(), system_prompt_template=_EMPTY_PROMPT)
