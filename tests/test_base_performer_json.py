"""Tests for BasePerformer._send_json — prompt-based fallback path (no schema).

The strict-mode path (with ``response_model``) is covered in
``test_send_json_validation.py``. These tests cover the schema-less branch
where ``_send_json`` returns a raw dict and decode failures hard-raise (the
old bracket-extraction recovery has been deleted).

Also covers ``_strip_markdown_fence`` (cast/_performer_retry.py) unit-level
edge cases: malformed/unclosed fences and fences without a language specifier.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from cast._performer_retry import _strip_markdown_fence
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

    @allure.story("Markdown fence recovery")
    @allure.title(
        "BasePerformer._send_json parses JSON wrapped in markdown fences on the fallback path",
    )
    @pytest.mark.asyncio
    async def test_fenced_json_parses_correctly(self):
        performer = self._make()
        fenced = '```json\n{"key": "val"}\n```'
        with patch.object(performer, _SEND_METHOD, new=AsyncMock(return_value=fenced)):
            output = await performer._send_json(_PROMPT)
        assert output == {"key": "val"}

    @allure.story("Decode failure")
    @allure.title(
        "BasePerformer._send_json raises LLMJSONError with the original fenced response "
        "in raw_response when the fence-stripped content is still not valid JSON",
    )
    @pytest.mark.asyncio
    async def test_fenced_invalid_json_preserves_raw_in_error(self):
        performer = self._make()
        fenced = "```json\nnot valid json\n```"
        with patch.object(performer, _SEND_METHOD, new=AsyncMock(return_value=fenced)):
            with pytest.raises(ValueError) as exc_info:
                await performer._send_json(_PROMPT)
        assert exc_info.value.raw_response.startswith("```")

    def _make(self) -> _JsonPerformer:
        return _JsonPerformer(llm_client=MagicMock(), system_prompt_template=_EMPTY_PROMPT)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("BasePerformer JSON send")
class TestStripMarkdownFence:
    """Unit tests for ``_strip_markdown_fence`` (cast/_performer_retry.py).

    Covers edge cases the integration-level tests above do not reach:
    malformed/unclosed fences and fences with no language specifier.
    The fallback path in ``_send_json_prompt_fallback`` calls this function
    before ``json.loads``; its behavior on malformed input determines
    whether downstream JSON decode errors carry a useful ``raw_response``.
    """

    @allure.story("Markdown fence recovery")
    @allure.title("_strip_markdown_fence strips a fence with no language specifier")
    def test_strips_fence_without_language(self):
        result = _strip_markdown_fence('```\n{"key": "val"}\n```')
        assert result == '{"key": "val"}'

    @allure.story("Markdown fence recovery")
    @allure.title("_strip_markdown_fence returns stripped original text when the closing fence is absent")
    def test_malformed_unclosed_fence_returns_stripped_original_text(self):
        malformed = '  ```json\n{"key": "val"}\n'
        assert _strip_markdown_fence(malformed) == malformed.strip()

    @allure.story("Markdown fence recovery")
    @allure.title("_strip_markdown_fence returns empty string for a fence whose body is all whitespace")
    def test_empty_body_fence_returns_empty_string(self):
        assert _strip_markdown_fence("```\n   \n```") == ""

    @allure.story("Markdown fence recovery")
    @allure.title("_strip_markdown_fence returns plain text unchanged when there is no fence")
    def test_plain_text_returned_unchanged(self):
        plain = '{"key": "val"}'
        assert _strip_markdown_fence(plain) == plain
