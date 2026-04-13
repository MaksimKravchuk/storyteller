"""Tests for llm.openai_client.OpenAIClient — SDK wiring, payload, streaming, formatting."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from llm import message as msg
from llm.openai_client import OpenAIClient

_OPENAI_CTOR = "openai.AsyncOpenAI"
_MODEL = "gpt-4"
_JSON_MODE_TYPE = "json_object"


def _make_response(
    content: str | None = "hello",
    prompt_tokens: int = 11,
    completion_tokens: int = 3,
    model: str = _MODEL,
) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
        model=model,
    )


def _install_sdk_mock(response: SimpleNamespace | None = None) -> tuple[MagicMock, AsyncMock]:
    """Patch AsyncOpenAI; return (sdk_class_mock, create_mock)."""
    sdk_class = MagicMock()
    sdk_instance = MagicMock()
    payload = _make_response() if response is None else response
    create_mock = AsyncMock(return_value=payload)
    sdk_instance.chat.completions.create = create_mock
    sdk_class.return_value = sdk_instance
    return sdk_class, create_mock


async def _stream_gen():
    yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="foo"))])
    yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None))])
    yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=""))])
    yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="bar"))])


def _user_msg(body: str = "hi") -> msg.Message:
    return msg.Message(role=msg.Role.USER, body=body)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("OpenAI client")
class TestOpenAIClient:
    @allure.story("Constructor")
    @allure.title("OpenAIClient instantiates AsyncOpenAI with the supplied api_key on construction")
    def test_constructor_wires_sdk(self) -> None:
        sdk_class, _ = _install_sdk_mock()
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="sk-xyz")
        sdk_class.assert_called_once_with(api_key="sk-xyz")
        assert client.model == _MODEL

    @allure.story("send_message")
    @allure.title("OpenAIClient.send_message builds a chat completion payload with model, messages, and token cap")
    @pytest.mark.asyncio
    async def test_send_message_payload(self) -> None:
        sdk_class, create_mock = _install_sdk_mock()
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="k")
            result = await client.send_message(messages=[_user_msg()], system_prompt="sys")

        kwargs = create_mock.call_args.kwargs
        assert kwargs["model"] == _MODEL
        assert kwargs["temperature"] == pytest.approx(0.7)
        assert kwargs["max_completion_tokens"] == 2048
        assert kwargs["messages"][0] == {"role": "system", "content": "sys"}
        assert kwargs["messages"][1] == {"role": "user", "content": "hi"}
        assert "response_format" not in kwargs
        assert result.body == "hello"
        assert result.usage == {"prompt_tokens": 11, "completion_tokens": 3}
        assert result.model == _MODEL

    @allure.story("send_message")
    @allure.title("OpenAIClient.send_message forwards temperature and max_tokens overrides to the SDK call")
    @pytest.mark.asyncio
    async def test_send_message_overrides(self) -> None:
        sdk_class, create_mock = _install_sdk_mock()
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="k")
            await client.send_message(messages=[_user_msg()], temperature=0.25, max_tokens=64)
        kwargs = create_mock.call_args.kwargs
        assert kwargs["temperature"] == pytest.approx(0.25)
        assert kwargs["max_completion_tokens"] == 64

    @allure.story("send_message")
    @allure.title("OpenAIClient.send_message passes response_format when the caller requests JSON mode")
    @pytest.mark.asyncio
    async def test_send_message_response_format(self) -> None:
        sdk_class, create_mock = _install_sdk_mock()
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="k")
            await client.send_message(
                messages=[_user_msg()],
                response_format={"type": _JSON_MODE_TYPE},
            )
        assert create_mock.call_args.kwargs["response_format"] == {"type": _JSON_MODE_TYPE}

    @allure.story("send_message")
    @allure.title("OpenAIClient.send_message returns an empty body and zeroed usage when the SDK response is blank")
    @pytest.mark.asyncio
    async def test_send_message_empty_response(self) -> None:
        blank = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None))],
            usage=None,
            model=_MODEL,
        )
        sdk_class, _ = _install_sdk_mock(blank)
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="k")
            result = await client.send_message(messages=[_user_msg("x")])
        assert result.body == ""
        assert result.usage == {"prompt_tokens": 0, "completion_tokens": 0}

    @allure.story("Streaming")
    @allure.title("OpenAIClient.send_message_streaming yields non-empty delta chunks and skips empty ones")
    @pytest.mark.asyncio
    async def test_send_message_streaming(self) -> None:
        sdk_class = MagicMock()
        sdk_instance = MagicMock()
        sdk_instance.chat.completions.create = AsyncMock(return_value=_stream_gen())
        sdk_class.return_value = sdk_instance
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="k")
            received: list[str] = []
            async for chunk in client.send_message_streaming(
                messages=[_user_msg()],
                system_prompt="sys",
            ):
                received.append(chunk)
        assert received == ["foo", "bar"]

    @allure.story("Message formatting")
    @allure.title("OpenAIClient._format_messages omits the system role when the system_prompt is empty")
    def test_format_messages_omits_empty_system(self) -> None:
        sdk_class, _ = _install_sdk_mock()
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="k")
            formatted = client._format_messages([_user_msg()], system_prompt="")
        assert formatted == [{"role": "user", "content": "hi"}]

    @allure.story("Message formatting")
    @allure.title("OpenAIClient._format_messages sanitizes message bodies so null bytes do not reach the SDK")
    def test_format_messages_sanitizes_bodies(self) -> None:
        sdk_class, _ = _install_sdk_mock()
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="k")
            formatted = client._format_messages(
                [_user_msg("hel\x00lo")],
                system_prompt="sy\x00s",
            )
        assert formatted[0] == {"role": "system", "content": "sys"}
        assert formatted[1] == {"role": "user", "content": "hello"}

    @allure.story("send_message")
    @allure.title("OpenAIClient.send_message logs the API error body and re-raises on a 400 Bad Request")
    @pytest.mark.asyncio
    async def test_send_message_api_error_is_logged_and_reraised(self) -> None:
        """A 400 Bad Request must be logged with the OpenAI error body, then re-raised.

        Regression test for the debuggability gap where an ``httpx.HTTPStatusError``
        was bubbling up to the caller without the OpenAI error message in the logs.
        """
        import httpx
        from loguru import logger
        from openai import BadRequestError

        error_body = {
            "error": {
                "message": "response_format of type 'json_object' is not supported with this model",
                "type": "invalid_request_error",
            },
        }
        fake_response = httpx.Response(
            status_code=400,
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        )
        bad_request = BadRequestError(
            message="400 Bad Request",
            response=fake_response,
            body=error_body,
        )

        sdk_class = MagicMock()
        sdk_instance = MagicMock()
        sdk_instance.chat.completions.create = AsyncMock(side_effect=bad_request)
        sdk_class.return_value = sdk_instance

        captured: list[str] = []
        sink_id = logger.add(lambda record: captured.append(str(record)), level="ERROR")
        try:
            with patch(_OPENAI_CTOR, sdk_class):
                client = OpenAIClient(model=_MODEL, api_key="k")
                with pytest.raises(BadRequestError):
                    await client.send_message(
                        messages=[_user_msg("trigger 400")],
                        system_prompt="director system prompt",
                        response_format={"type": _JSON_MODE_TYPE},
                    )
        finally:
            logger.remove(sink_id)

        assert any("OpenAI API error" in entry for entry in captured)
        assert any(_MODEL in entry for entry in captured)
        assert any("json_object" in entry for entry in captured)
