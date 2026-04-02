"""Tests for BasePerformer._send_json — JSON parsing, retries, and bracket extraction."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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


class TestSendJson:
    @pytest.mark.asyncio
    async def test_returns_dict_on_success(self):
        performer = self._make()
        with patch.object(performer, _SEND_METHOD, new=AsyncMock(return_value='{"key": "value"}')):
            output = await performer._send_json(_PROMPT)
        assert output == {"key": "value"}

    @pytest.mark.asyncio
    async def test_bracket_extraction_fallback(self):
        performer = self._make()
        with patch.object(performer, _SEND_METHOD, new=AsyncMock(return_value='noise {"extracted": true} noise')):
            extracted = await performer._send_json(_PROMPT, retries=0)
        assert extracted == {"extracted": True}

    @pytest.mark.asyncio
    async def test_raises_when_all_retries_fail(self):
        performer = self._make()
        with patch.object(performer, _SEND_METHOD, new=AsyncMock(return_value="not json at all")) as mock_send:
            with pytest.raises(ValueError, match="failed to produce valid JSON"):
                await performer._send_json(_PROMPT, retries=2)
        assert mock_send.call_count == 3

    @pytest.mark.asyncio
    async def test_invalid_inner_braces(self):
        performer = self._make()
        with patch.object(performer, _SEND_METHOD, new=AsyncMock(return_value="prefix {broken json} suffix")):
            with pytest.raises(ValueError, match="failed to produce valid JSON"):
                await performer._send_json(_PROMPT, retries=0)

    @pytest.mark.asyncio
    async def test_non_json_exception_propagates(self):
        performer = self._make()
        with patch.object(performer, _SEND_METHOD, new=_bad_send):
            with pytest.raises(UnicodeDecodeError):
                await performer._send_json(_PROMPT, retries=0)

    def _make(self) -> _JsonPerformer:
        return _JsonPerformer(llm_client=MagicMock(), system_prompt_template=_EMPTY_PROMPT)
