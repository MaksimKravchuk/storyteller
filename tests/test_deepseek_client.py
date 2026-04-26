"""Tests for llm.deepseek_client.DeepSeekClient — base_url + inheritance."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import allure
import pytest

from llm.deepseek_client import DeepSeekClient

_SDK_CTOR = "openai.AsyncOpenAI"

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("DeepSeek provider"),
]


@allure.story("Base URL")
@allure.title("DeepSeekClient constructs the AsyncOpenAI SDK with the DeepSeek base_url")
def test_constructs_with_deepseek_base_url() -> None:
    sdk_class = MagicMock()
    sdk_class.return_value = MagicMock()
    with patch(_SDK_CTOR, sdk_class):
        DeepSeekClient(model="deepseek-chat", api_key="ds-key")

    final_kwargs = sdk_class.call_args_list[-1].kwargs
    assert final_kwargs["base_url"] == "https://api.deepseek.com/v1"
    assert final_kwargs["api_key"] == "ds-key"


@allure.story("Inheritance")
@allure.title("DeepSeekClient inherits model / api_key / temperature bookkeeping from OpenAIClient")
def test_inherits_openai_bookkeeping() -> None:
    with patch(_SDK_CTOR, MagicMock()):
        client = DeepSeekClient(
            model="deepseek-reasoner",
            api_key="ds-xyz",
            temperature=0.2,
            max_tokens=4096,
        )
    assert client.model == "deepseek-reasoner"
    assert client.api_key == "ds-xyz"
    assert client.temperature == pytest.approx(0.2)
    assert client.max_tokens == 4096
