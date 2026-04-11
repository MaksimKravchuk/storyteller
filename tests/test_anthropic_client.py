"""Tests for llm.anthropic_client.AnthropicClient — SDK wiring, blocks, streaming, roles."""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import partial
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from llm import message as msg
from llm.anthropic_client import AnthropicClient

_ANTHROPIC_CTOR = "anthropic.AsyncAnthropic"
_MODEL = "claude-sonnet-4-20250514"


def _text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _tool_block() -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", text="should be ignored")


def _make_response(
    blocks: list[SimpleNamespace] | None = None,
    input_tokens: int = 7,
    output_tokens: int = 2,
) -> SimpleNamespace:
    content_blocks = [_text_block("hello")] if blocks is None else blocks
    return SimpleNamespace(
        content=content_blocks,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        model=_MODEL,
    )


def _install_sdk_mock(response: SimpleNamespace | None = None) -> tuple[MagicMock, AsyncMock]:
    sdk_class = MagicMock()
    sdk_instance = MagicMock()
    payload = _make_response() if response is None else response
    create_mock = AsyncMock(return_value=payload)
    sdk_instance.messages.create = create_mock
    sdk_class.return_value = sdk_instance
    return sdk_class, create_mock


async def _text_gen(chunks: list[str]):
    for chunk in chunks:
        yield chunk


@asynccontextmanager
async def _fake_stream_cm(state, **kwargs):
    state["captured"].append(kwargs)
    yield SimpleNamespace(text_stream=_text_gen(state["chunks"]))


def _install_streaming_mock(chunks: list[str]) -> tuple[MagicMock, list[dict]]:
    """Install an AsyncAnthropic mock whose messages.stream() is an async context manager."""
    state: dict = {"captured": [], "chunks": chunks}
    sdk_class = MagicMock()
    sdk_instance = MagicMock()
    sdk_instance.messages.stream = partial(_fake_stream_cm, state)
    sdk_class.return_value = sdk_instance
    return sdk_class, state["captured"]


def _user_msg(body: str = "hi") -> msg.Message:
    return msg.Message(role=msg.Role.USER, body=body)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Anthropic client")
class TestAnthropicClient:
    @allure.story("Constructor")
    @allure.title("AnthropicClient instantiates AsyncAnthropic with the supplied api_key on construction")
    def test_constructor_wires_sdk(self) -> None:
        sdk_class, _ = _install_sdk_mock()
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="ak-xyz")
        sdk_class.assert_called_once_with(api_key="ak-xyz")
        assert client.model == _MODEL

    @allure.story("send_message")
    @allure.title("AnthropicClient.send_message concatenates text blocks and ignores non-text content blocks")
    @pytest.mark.asyncio
    async def test_send_message_text_block_concatenation(self) -> None:
        response = _make_response(
            blocks=[_text_block("Hello, "), _tool_block(), _text_block("world!")],
        )
        sdk_class, create_mock = _install_sdk_mock(response)
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            result = await client.send_message(
                messages=[_user_msg()],
                system_prompt="you are helpful",
            )
        kwargs = create_mock.call_args.kwargs
        assert kwargs["model"] == _MODEL
        assert kwargs["system"] == "you are helpful"
        assert kwargs["temperature"] == pytest.approx(0.7)
        assert kwargs["max_tokens"] == 2048
        assert result.body == "Hello, world!"
        assert result.usage == {"prompt_tokens": 7, "completion_tokens": 2}
        assert result.model == _MODEL

    @allure.story("send_message")
    @allure.title("AnthropicClient.send_message omits the system kwarg when the system_prompt is empty")
    @pytest.mark.asyncio
    async def test_send_message_no_system(self) -> None:
        sdk_class, create_mock = _install_sdk_mock()
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            await client.send_message(messages=[_user_msg()])
        assert "system" not in create_mock.call_args.kwargs

    @allure.story("send_message")
    @allure.title("AnthropicClient.send_message forwards temperature and max_tokens overrides to the SDK call")
    @pytest.mark.asyncio
    async def test_send_message_overrides(self) -> None:
        sdk_class, create_mock = _install_sdk_mock()
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            await client.send_message(
                messages=[_user_msg()],
                temperature=0.25,
                max_tokens=128,
            )
        kwargs = create_mock.call_args.kwargs
        assert kwargs["temperature"] == pytest.approx(0.25)
        assert kwargs["max_tokens"] == 128

    @allure.story("Streaming")
    @allure.title("AnthropicClient.send_message_streaming yields text chunks from the SDK stream context manager")
    @pytest.mark.asyncio
    async def test_streaming_yields_chunks(self) -> None:
        sdk_class, captured = _install_streaming_mock(["foo", "bar", "baz"])
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            received: list[str] = []
            async for chunk in client.send_message_streaming(
                messages=[_user_msg()],
                system_prompt="sys",
            ):
                received.append(chunk)
        assert received == ["foo", "bar", "baz"]
        assert captured[0]["system"] == "sys"

    @allure.story("Streaming")
    @allure.title("AnthropicClient.send_message_streaming omits the system kwarg when the system_prompt is empty")
    @pytest.mark.asyncio
    async def test_streaming_omits_empty_system(self) -> None:
        sdk_class, captured = _install_streaming_mock(["x"])
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            received = [chunk async for chunk in client.send_message_streaming(messages=[_user_msg()])]
        assert received == ["x"]
        assert "system" not in captured[0]

    @allure.story("Message formatting")
    @allure.title("AnthropicClient._format_messages maps Role.USER to 'user' and Role.ASSISTANT to 'assistant'")
    def test_format_messages_role_mapping(self) -> None:
        sdk_class, _ = _install_sdk_mock()
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            formatted = client._format_messages(
                [
                    msg.Message(role=msg.Role.USER, body="u"),
                    msg.Message(role=msg.Role.ASSISTANT, body="a"),
                ],
            )
        assert formatted == [
            {"role": "user", "content": "u"},
            {"role": "assistant", "content": "a"},
        ]

    @allure.story("Message formatting")
    @allure.title("AnthropicClient._format_messages maps Role.SYSTEM to 'assistant' (documented current behavior)")
    def test_format_messages_system_role_maps_to_assistant(self) -> None:
        sdk_class, _ = _install_sdk_mock()
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            formatted = client._format_messages(
                [msg.Message(role=msg.Role.SYSTEM, body="s")],
            )
        assert formatted == [{"role": "assistant", "content": "s"}]
