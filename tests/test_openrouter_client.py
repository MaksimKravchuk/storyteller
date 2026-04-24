"""Tests for llm.openrouter_client.OpenRouterClient — base_url + headers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import allure
import pytest

from llm.openrouter_client import OpenRouterClient

_SDK_CTOR = "openai.AsyncOpenAI"

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("OpenRouter provider"),
]


@allure.story("Base URL")
@allure.title("OpenRouterClient constructs the AsyncOpenAI SDK with the OpenRouter base_url")
def test_constructs_with_openrouter_base_url() -> None:
    sdk_class = MagicMock()
    sdk_class.return_value = MagicMock()
    with patch(_SDK_CTOR, sdk_class):
        OpenRouterClient(model="deepseek/deepseek-chat-v3.1", api_key="or-key")

    # Two calls: OpenAIClient.__init__ first (bare), then OpenRouterClient
    # replaces the client with the base_url-configured one. We assert the
    # final call is the OpenRouter one.
    final_kwargs = sdk_class.call_args_list[-1].kwargs
    assert final_kwargs["base_url"] == "https://openrouter.ai/api/v1"
    assert final_kwargs["api_key"] == "or-key"


@allure.story("Attribution headers")
@allure.title("OpenRouterClient attaches HTTP-Referer and X-Title attribution headers")
def test_sends_attribution_headers() -> None:
    sdk_class = MagicMock()
    sdk_class.return_value = MagicMock()
    with patch(_SDK_CTOR, sdk_class):
        OpenRouterClient(model="google/gemini-2.5-pro", api_key="or-key")

    headers = sdk_class.call_args_list[-1].kwargs["default_headers"]
    assert "HTTP-Referer" in headers
    assert "X-Title" in headers
    assert headers["X-Title"] == "Storyteller"


@allure.story("Inheritance")
@allure.title("OpenRouterClient inherits model / api_key / temperature bookkeeping from OpenAIClient")
def test_inherits_openai_bookkeeping() -> None:
    with patch(_SDK_CTOR, MagicMock()):
        client = OpenRouterClient(
            model="x-ai/grok-4-fast",
            api_key="or-xyz",
            temperature=0.3,
            max_tokens=777,
        )
    assert client.model == "x-ai/grok-4-fast"
    assert client.api_key == "or-xyz"
    assert client.temperature == pytest.approx(0.3)
    assert client.max_tokens == 777
