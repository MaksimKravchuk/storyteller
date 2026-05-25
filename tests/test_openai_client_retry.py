"""Tests for OpenAIClient._call_with_retry — exponential backoff on 5xx and transient errors."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import httpx
import pytest
from openai import APITimeoutError, BadRequestError, InternalServerError

from cast import _reliability_metrics
from llm import message as msg
from llm.openai_client import OpenAIClient, _call_with_retry

_OPENAI_CTOR = "openai.AsyncOpenAI"
_MODEL = "gpt-4"


def _make_openai_5xx(message: str = "Service temporarily unavailable.") -> InternalServerError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(503, request=request)
    return InternalServerError(message, response=response, body=None)


def _make_openai_400() -> BadRequestError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(400, request=request)
    return BadRequestError("bad request", response=response, body=None)


def _make_openai_timeout() -> APITimeoutError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return APITimeoutError(request=request)


def _make_response(content: str = "hello") -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=5, completion_tokens=2),
        model=_MODEL,
    )


def _user_msg(body: str = "hi") -> msg.Message:
    return msg.Message(role=msg.Role.USER, body=body)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("OpenAI client — retry/backoff")
class TestOpenAIClientRetry:
    @allure.story("Retry on 5xx")
    @allure.title("OpenAIClient.send_message retries on OpenAI 5xx and returns the eventual success")
    @pytest.mark.asyncio
    async def test_send_message_retries_5xx_then_succeeds(self) -> None:
        sdk_class = MagicMock()
        sdk_instance = MagicMock()
        create_mock = AsyncMock(side_effect=[_make_openai_5xx(), _make_openai_5xx(), _make_response()])
        sdk_instance.chat.completions.create = create_mock
        sdk_class.return_value = sdk_instance
        with (
            patch(_OPENAI_CTOR, sdk_class),
            patch("llm.openai_client.asyncio.sleep", new=AsyncMock()) as sleep_mock,
        ):
            _reliability_metrics.reset_counters()
            client = OpenAIClient(model=_MODEL, api_key="k")
            result = await client.send_message(messages=[_user_msg()])
        assert create_mock.await_count == 3
        assert result.body == "hello"
        # Backoff schedule: 2.0s, 4.0s
        assert [call.args[0] for call in sleep_mock.await_args_list] == [
            pytest.approx(2.0),
            pytest.approx(4.0),
        ]
        counters = _reliability_metrics.snapshot_counters()
        assert counters.get(("openai_client", "validation_retry"), 0) == 2

    @allure.story("Retry on 5xx")
    @allure.title("OpenAIClient.send_message stops retrying after _RETRY_MAX_ATTEMPTS and raises the last 5xx")
    @pytest.mark.asyncio
    async def test_send_message_5xx_exhausts_retries(self) -> None:
        sdk_class = MagicMock()
        sdk_instance = MagicMock()
        final_error = _make_openai_5xx("final")
        create_mock = AsyncMock(side_effect=[_make_openai_5xx(), _make_openai_5xx(), final_error])
        sdk_instance.chat.completions.create = create_mock
        sdk_class.return_value = sdk_instance
        with (
            patch(_OPENAI_CTOR, sdk_class),
            patch("llm.openai_client.asyncio.sleep", new=AsyncMock()),
        ):
            client = OpenAIClient(model=_MODEL, api_key="k")
            with pytest.raises(InternalServerError) as exc_info:
                await client.send_message(messages=[_user_msg()])
        assert create_mock.await_count == 3
        assert exc_info.value is final_error

    @allure.story("Retry on 5xx")
    @allure.title("_call_with_retry does not retry 4xx errors and propagates them on the first attempt")
    @pytest.mark.asyncio
    async def test_call_with_retry_does_not_retry_4xx(self) -> None:
        bad = _make_openai_400()
        create = AsyncMock(side_effect=bad)
        sleep_mock = AsyncMock()
        with patch("llm.openai_client.asyncio.sleep", new=sleep_mock):
            with pytest.raises(BadRequestError):
                await _call_with_retry(create)
        assert create.await_count == 1
        sleep_mock.assert_not_awaited()

    @allure.story("Retry on 5xx")
    @allure.title("_call_with_retry retries on APITimeoutError (transient network error) with backoff")
    @pytest.mark.asyncio
    async def test_call_with_retry_retries_on_timeout(self) -> None:
        create = AsyncMock(side_effect=[_make_openai_timeout(), _make_openai_timeout(), _make_response()])
        with patch("llm.openai_client.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            result = await _call_with_retry(create)
        assert create.await_count == 3
        assert result.choices[0].message.content == "hello"
        assert [call.args[0] for call in sleep_mock.await_args_list] == [
            pytest.approx(2.0),
            pytest.approx(4.0),
        ]
