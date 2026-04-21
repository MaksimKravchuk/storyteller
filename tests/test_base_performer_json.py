"""Tests for BasePerformer._send_json — prompt-based fallback path (no schema).

The strict-mode path (with ``response_model``) is covered in
``test_send_json_validation.py``. These tests cover the schema-less branch
where ``_send_json`` returns a raw dict and decode failures hard-raise (the
old bracket-extraction recovery has been deleted).
"""

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

    @allure.story("Decode failure")
    @allure.title(
        "BasePerformer._send_json raises immediately on the fallback path when the LLM returns "
        "non-JSON; bracket extraction has been removed",
    )
    @pytest.mark.asyncio
    async def test_decode_failure_raises_immediately_on_fallback(self):
        performer = self._make()
        with patch.object(
            performer,
            _SEND_METHOD,
            new=AsyncMock(return_value="not json at all"),
        ) as mock_send:
            with pytest.raises(ValueError, match="non-JSON response on fallback path"):
                await performer._send_json(_PROMPT, retries=2)
        assert mock_send.call_count == 1

    @allure.story("Decode failure")
    @allure.title(
        "BasePerformer._send_json no longer recovers JSON embedded in prose via bracket extraction; "
        "the call raises instead",
    )
    @pytest.mark.asyncio
    async def test_decode_failure_does_not_extract_from_prose(self):
        performer = self._make()
        body = 'noise {"extracted": true} noise'
        with patch.object(performer, _SEND_METHOD, new=AsyncMock(return_value=body)):
            with pytest.raises(ValueError, match="non-JSON response on fallback path"):
                await performer._send_json(_PROMPT, retries=0)

    @allure.story("Error handling")
    @allure.title(
        "Non-JSON exceptions raised by _send propagate out of _send_json instead of being swallowed as parse errors",
    )
    @pytest.mark.asyncio
    async def test_non_json_exception_propagates(self):
        performer = self._make()
        with patch.object(performer, _SEND_METHOD, new=_bad_send):
            with pytest.raises(UnicodeDecodeError):
                await performer._send_json(_PROMPT, retries=0)

    def _make(self) -> _JsonPerformer:
        return _JsonPerformer(llm_client=MagicMock(), system_prompt_template=_EMPTY_PROMPT)
