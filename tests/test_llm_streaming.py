"""Tests for provider ``stream_message``: OpenAI chunk streams and Anthropic message streams."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from llm.anthropic_client import AnthropicClient
from llm.message import Message, Role
from llm.openai_client import OpenAIClient
from tests._turn_stream_helpers import RecordingSink
from tests.test_anthropic_client import _make_anthropic_5xx

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("LLM streaming"),
]

_USER = (Message(role=Role.USER, body="hi"),)


def _openai_chunk(text: str | None, usage: Any = None) -> SimpleNamespace:
    choices = [] if text is None else [SimpleNamespace(delta=SimpleNamespace(content=text))]
    return SimpleNamespace(model="gpt-test", usage=usage, choices=choices)


async def _aiter(items: list[Any]) -> AsyncIterator[Any]:
    for item in items:
        yield item


class _AnthropicStream:
    """Stand-in for the SDK's ``messages.stream`` async context manager."""

    def __init__(self, texts: list[str], final: SimpleNamespace) -> None:
        self.text_stream = _aiter(texts)
        self._final = final

    async def __aenter__(self) -> "_AnthropicStream":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def get_final_message(self) -> SimpleNamespace:
        return self._final


class _FailingAnthropicStream:
    """``messages.stream`` manager whose request fails before any text arrives."""

    async def __aenter__(self) -> None:
        raise _make_anthropic_5xx()

    async def __aexit__(self, *exc: object) -> bool:
        return False


def _final_message(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=5, output_tokens=3),
        model="claude-test",
    )


@allure.story("OpenAI")
@allure.title("OpenAI stream_message forwards each content delta and assembles body, usage and model")
@pytest.mark.asyncio
async def test_openai_stream_message() -> None:
    usage = SimpleNamespace(prompt_tokens=9, completion_tokens=4)
    chunks = [_openai_chunk("Dawn "), _openai_chunk(""), _openai_chunk("breaks."), _openai_chunk(None, usage)]
    sdk_class = MagicMock()
    create = AsyncMock(return_value=_aiter(chunks))
    sdk_class.return_value.chat.completions.create = create
    sink = RecordingSink()

    with patch("openai.AsyncOpenAI", sdk_class):
        client = OpenAIClient(model="gpt-test", api_key="k")
        response = await client.stream_message(list(_USER), on_delta=sink.delta, system_prompt="sys", max_tokens=50)

    assert sink.deltas == ["Dawn ", "breaks."]
    assert response.body == "Dawn breaks."
    assert response.usage == {"prompt_tokens": 9, "completion_tokens": 4}
    assert response.model == "gpt-test"
    sent = create.call_args.kwargs
    assert sent["stream"] is True
    assert sent["stream_options"] == {"include_usage": True}
    assert sent["max_completion_tokens"] == 50
    assert "response_format" not in sent


@allure.story("Anthropic")
@allure.title("Anthropic stream_message forwards text deltas and builds the response from the final message")
@pytest.mark.asyncio
async def test_anthropic_stream_message() -> None:
    sdk_class = MagicMock()
    stream = MagicMock(return_value=_AnthropicStream(["Dusk ", "falls."], _final_message("Dusk falls.")))
    sdk_class.return_value.messages.stream = stream
    sink = RecordingSink()

    with patch("anthropic.AsyncAnthropic", sdk_class):
        client = AnthropicClient(model="claude-test", api_key="k")
        response = await client.stream_message(list(_USER), on_delta=sink.delta, system_prompt="sys")

    assert sink.deltas == ["Dusk ", "falls."]
    assert response.body == "Dusk falls."
    assert response.usage == {"prompt_tokens": 5, "completion_tokens": 3}
    assert stream.call_args.kwargs["system"] == "sys"


@allure.story("Anthropic")
@allure.title("Anthropic stream_message retries a 5xx raised while opening the stream, before any text")
@pytest.mark.asyncio
async def test_anthropic_stream_message_retries_opening() -> None:
    sdk_class = MagicMock()
    healthy = _AnthropicStream(["Dawn."], _final_message("Dawn."))
    stream = MagicMock(side_effect=[_FailingAnthropicStream(), healthy])
    sdk_class.return_value.messages.stream = stream
    sink = RecordingSink()

    with patch("anthropic.AsyncAnthropic", sdk_class), patch("llm.anthropic_client.asyncio.sleep", new=AsyncMock()):
        client = AnthropicClient(model="claude-test", api_key="k")
        response = await client.stream_message(list(_USER), on_delta=sink.delta)

    assert stream.call_count == 2
    assert sink.deltas == ["Dawn."]
    assert response.body == "Dawn."
