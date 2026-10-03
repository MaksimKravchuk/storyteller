"""Tests for the request shape AnthropicClient sends to always-thinking Claude models."""

from __future__ import annotations

from unittest.mock import patch

import allure
import pytest

from llm import message as msg
from llm.anthropic_client import AnthropicClient
from tests.test_anthropic_client import _ANTHROPIC_CTOR, _install_sdk_mock

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Anthropic client — reasoning models"),
    allure.story("Sampling and effort"),
]


def _user_msg() -> msg.Message:
    return msg.Message(role=msg.Role.USER, body="hi")


@allure.title("Opus 5.5 / Sonnet 5.5 requests drop temperature, which they reject, and pin effort to low")
@pytest.mark.parametrize("model", ["claude-opus-5-5", "claude-sonnet-5-5"])
@pytest.mark.asyncio
async def test_reasoning_models_drop_temperature_and_pin_low_effort(model: str) -> None:
    sdk_class, create_mock = _install_sdk_mock()
    with patch(_ANTHROPIC_CTOR, sdk_class):
        client = AnthropicClient(model=model, api_key="k")
        await client.send_message(messages=[_user_msg()], temperature=0.2)
    kwargs = create_mock.call_args.kwargs
    assert "temperature" not in kwargs
    assert kwargs["output_config"] == {"effort": "low"}


@allure.title("Haiku 4.5 keeps its temperature and gets no effort setting")
@pytest.mark.asyncio
async def test_haiku_keeps_temperature() -> None:
    sdk_class, create_mock = _install_sdk_mock()
    with patch(_ANTHROPIC_CTOR, sdk_class):
        client = AnthropicClient(model="claude-haiku-4-5", api_key="k")
        await client.send_message(messages=[_user_msg()], temperature=0.2)
    kwargs = create_mock.call_args.kwargs
    assert kwargs["temperature"] == pytest.approx(0.2)
    assert "output_config" not in kwargs
