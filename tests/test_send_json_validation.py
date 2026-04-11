"""Tests for BasePerformer._send_json validation-retry loop.

Focused on the pydantic self-correcting path: a response that parses
as JSON but fails ``model_validate`` should trigger a retry in which
the assistant's bad payload and a user feedback message are appended
to the conversation, and the recursive call must pass the schema through.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest
from pydantic import BaseModel

from cast.base_performer_class import BasePerformer
from llm.message import Role
from prompts.base_template import PromptTemplate

_SEND_METHOD = "_send"
_PROMPT = "prompt"
_EMPTY_PROMPT = PromptTemplate([])
_VALIDATION_ERRORS_MARKER = "failed schema validation"


class _WidgetResponse(BaseModel):
    """Minimal schema used to exercise the validation retry branch."""

    count: int
    label: str = "default"


class _JsonPerformer(BasePerformer):
    async def act(self, input_data: Any, context: dict) -> Any:
        return await self._send_json(input_data, response_model=_WidgetResponse)


def _make_performer() -> _JsonPerformer:
    return _JsonPerformer(llm_client=MagicMock(), system_prompt_template=_EMPTY_PROMPT)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("BasePerformer JSON send — validation retry")
class TestSendJsonValidationRetry:
    @allure.story("Self-correcting retry")
    @allure.title(
        "_send_json retries when the parsed JSON fails model_validate and feeds the "
        "error back to the LLM in the next attempt's conversation",
    )
    @pytest.mark.asyncio
    async def test_validation_failure_retries_and_recovers(self) -> None:
        performer = _make_performer()
        # First attempt: valid JSON, wrong type for ``count`` → ValidationError.
        # Second attempt: correct payload.
        bad_response = json.dumps({"count": "not-a-number", "label": "widget"})
        good_response = json.dumps({"count": 3, "label": "widget"})
        send_mock = AsyncMock(side_effect=[bad_response, good_response])
        with patch.object(performer, _SEND_METHOD, new=send_mock):
            result = await performer._send_json(_PROMPT, response_model=_WidgetResponse)

        assert isinstance(result, _WidgetResponse)
        assert result.count == 3
        assert result.label == "widget"
        assert send_mock.call_count == 2

        # The second _send call must have received the bad payload and a user feedback
        # message appended to the conversation.
        second_call_kwargs = send_mock.call_args_list[1].kwargs
        retry_conversation = second_call_kwargs.get("conversation") or []
        assert len(retry_conversation) == 2
        assert retry_conversation[0].role == Role.ASSISTANT
        assert retry_conversation[0].body == bad_response
        assert retry_conversation[1].role == Role.USER
        assert "failed schema validation" in retry_conversation[1].body

    @allure.story("Self-correcting retry")
    @allure.title(
        "_send_json raises a ValueError after exhausting retries when every attempt "
        "produces JSON that fails schema validation",
    )
    @pytest.mark.asyncio
    async def test_validation_failure_exhausts_retries(self) -> None:
        performer = _make_performer()
        bad_response = json.dumps({"count": "nope"})
        send_mock = AsyncMock(return_value=bad_response)
        with patch.object(performer, _SEND_METHOD, new=send_mock):
            with pytest.raises(ValueError, match=_VALIDATION_ERRORS_MARKER):
                await performer._send_json(_PROMPT, retries=1, response_model=_WidgetResponse)
        # retries=1 → 2 total attempts.
        assert send_mock.call_count == 2

    @allure.story("Self-correcting retry")
    @allure.title("_send_json does not mutate the caller's conversation list on validation retry")
    @pytest.mark.asyncio
    async def test_caller_conversation_is_not_mutated(self) -> None:
        performer = _make_performer()
        bad_response = json.dumps({"count": "nope"})
        good_response = json.dumps({"count": 1})
        caller_conversation: list = []
        send_mock = AsyncMock(side_effect=[bad_response, good_response])
        with patch.object(performer, _SEND_METHOD, new=send_mock):
            await performer._send_json(
                _PROMPT,
                conversation=caller_conversation,
                response_model=_WidgetResponse,
            )
        assert caller_conversation == []
