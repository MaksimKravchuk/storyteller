"""Tests for BasePerformer._send_json validation-retry loop and strict-mode path.

Covers two paths:

1. **Strict path**: when ``response_model`` is provided, ``_send_json``
   should call the LLM with a schema-bearing ``OutputFormat`` and trust the
   provider-enforced shape (no retry). Falls back to the prompt path on
   ``NotImplementedError``.

2. **Prompt-based fallback**: a response that parses as JSON but fails
   ``model_validate`` triggers a retry in which the assistant's bad payload
   and a user feedback message are appended to the conversation; the caller's
   conversation list is never mutated.
"""

from __future__ import annotations

import json
from contextlib import ExitStack
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest
from pydantic import BaseModel

from cast.base_performer_class import BasePerformer
from llm.message import LLMResponse, Role
from prompts.base_template import PromptTemplate

_SEND_METHOD = "_send"
_STRICT_HELPER = "cast.base_performer_class._send_json_strict"
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


def _make_performer(llm_client: Any | None = None) -> _JsonPerformer:
    return _JsonPerformer(
        llm_client=llm_client or MagicMock(),
        system_prompt_template=_EMPTY_PROMPT,
    )


def _llm_response(body: str) -> LLMResponse:
    return LLMResponse(body=body, usage={}, model="test-model")


def _force_fallback() -> Any:
    """Patch the strict path to raise so ``_send_json`` takes the fallback branch."""
    return patch(
        _STRICT_HELPER,
        new=AsyncMock(side_effect=NotImplementedError("forced fallback for test")),
    )


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
        bad_response = json.dumps({"count": "not-a-number", "label": "widget"})
        good_response = json.dumps({"count": 3, "label": "widget"})
        send_mock = AsyncMock(side_effect=[bad_response, good_response])
        with ExitStack() as stack:
            stack.enter_context(_force_fallback())
            stack.enter_context(patch.object(performer, _SEND_METHOD, new=send_mock))
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
        with ExitStack() as stack:
            stack.enter_context(_force_fallback())
            stack.enter_context(patch.object(performer, _SEND_METHOD, new=send_mock))
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
        with ExitStack() as stack:
            stack.enter_context(_force_fallback())
            stack.enter_context(patch.object(performer, _SEND_METHOD, new=send_mock))
            await performer._send_json(
                _PROMPT,
                conversation=caller_conversation,
                response_model=_WidgetResponse,
            )
        assert caller_conversation == []


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("BasePerformer JSON send — strict structured outputs")
class TestSendJsonStrictMode:
    @allure.story("Strict path success")
    @allure.title(
        "_send_json passes an OutputFormat carrying the model's JSON schema and class name "
        "to the LLM client and returns the validated instance in a single call",
    )
    @pytest.mark.asyncio
    async def test_strict_mode_success_no_retry(self) -> None:
        llm = MagicMock()
        llm.model = "test-model"
        llm.send_message = AsyncMock(return_value=_llm_response(json.dumps({"count": 7})))
        performer = _make_performer(llm)

        result = await performer._send_json(_PROMPT, response_model=_WidgetResponse)

        assert isinstance(result, _WidgetResponse)
        assert result.count == 7
        assert llm.send_message.call_count == 1
        output_format = llm.send_message.call_args.kwargs["output_format"]
        assert output_format.schema is not None
        assert output_format.schema == _WidgetResponse.model_json_schema()
        assert output_format.schema_name == "_WidgetResponse"

    @allure.story("Strict path fallback")
    @allure.title(
        "_send_json falls back to the prompt-based JSON path when the LLM client raises "
        "NotImplementedError on the strict attempt",
    )
    @pytest.mark.asyncio
    async def test_strict_mode_notimplemented_falls_back_to_prompt_path(self) -> None:
        llm = MagicMock()
        llm.model = "test-model"
        llm.send_message = AsyncMock(
            side_effect=[
                NotImplementedError("structured outputs not supported"),
                _llm_response(json.dumps({"count": 4, "label": "ok"})),
            ],
        )
        performer = _make_performer(llm)

        result = await performer._send_json(_PROMPT, response_model=_WidgetResponse)

        assert isinstance(result, _WidgetResponse)
        assert result.count == 4
        assert result.label == "ok"
        assert llm.send_message.call_count == 2
        call_history = llm.send_message.call_args_list
        first_output = call_history[0].kwargs["output_format"]
        second_output = call_history[1].kwargs["output_format"]
        assert first_output.schema is not None
        assert second_output.schema is None
        assert second_output.response_format == {"type": "json_object"}

    @allure.story("Strict path failure")
    @allure.title(
        "_send_json raises ValueError without retry when the strict response is structurally "
        "invalid (provider violated its own contract)",
    )
    @pytest.mark.asyncio
    async def test_strict_mode_validation_failure_raises_without_retry(self) -> None:
        llm = MagicMock()
        llm.model = "test-model"
        llm.send_message = AsyncMock(return_value=_llm_response(json.dumps({"count": "bad"})))
        performer = _make_performer(llm)

        with pytest.raises(ValueError, match="Strict structured output failed validation"):
            await performer._send_json(_PROMPT, response_model=_WidgetResponse)
        assert llm.send_message.call_count == 1

    @allure.story("Strict path fallback")
    @allure.title(
        "After NotImplementedError forces a fallback, validation-retry recursion stays on the "
        "prompt-fallback path (no second strict attempt)",
    )
    @pytest.mark.asyncio
    async def test_fallback_recursion_does_not_reattempt_strict(self) -> None:
        llm = MagicMock()
        llm.model = "test-model"
        # 1) strict attempt raises; 2) prompt-fallback returns invalid payload (validation
        # error); 3) prompt-fallback retry returns valid payload. Only one
        # NotImplementedError-raising call should happen overall.
        llm.send_message = AsyncMock(
            side_effect=[
                NotImplementedError("structured outputs not supported"),
                _llm_response(json.dumps({"count": "bad"})),
                _llm_response(json.dumps({"count": 9})),
            ],
        )
        performer = _make_performer(llm)

        result = await performer._send_json(_PROMPT, response_model=_WidgetResponse)

        assert isinstance(result, _WidgetResponse)
        assert result.count == 9
        assert llm.send_message.call_count == 3
        # All calls after the first must be on the prompt-fallback path.
        for call in llm.send_message.call_args_list[1:]:
            output_format = call.kwargs["output_format"]
            assert output_format.schema is None
            assert output_format.response_format == {"type": "json_object"}
