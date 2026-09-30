"""Tests for the reasoning_effort pin OpenAIClient sends for GPT-6 Luna (ADR-0018)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from config import Config, resolve_model_config
from llm import message as msg
from llm.base_client import OutputFormat
from llm.factory import create_llm_client
from llm.message import Tool
from llm.openai_client import OpenAIClient

_OPENAI_CTOR = "openai.AsyncOpenAI"
_GPT6_LUNA = "gpt-6-luna"
_ROLE_MODEL_FIELDS = ("director_model", "agent_model", "narrator_model", "dramaturge_model")

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("OpenAI client — reasoning effort"),
    allure.story("Reasoning effort"),
]


def _install_sdk_mock() -> tuple[MagicMock, AsyncMock]:
    """Patch target for AsyncOpenAI; return (sdk_class_mock, create_mock)."""
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        model=_GPT6_LUNA,
    )
    create_mock = AsyncMock(return_value=response)
    sdk_instance = MagicMock()
    sdk_instance.chat.completions.create = create_mock
    sdk_class = MagicMock(return_value=sdk_instance)
    return sdk_class, create_mock


def _user_msg() -> msg.Message:
    return msg.Message(role=msg.Role.USER, body="hi")


@allure.title(
    "gpt-6-luna tool-call requests pin reasoning_effort to none so temperature and Chat Completions "
    "function calling stay valid",
)
@pytest.mark.asyncio
async def test_gpt6_luna_pins_reasoning_effort_none() -> None:
    sdk_class, create_mock = _install_sdk_mock()
    tool = Tool(name="move", description="Player moves.", parameters_schema={"type": "object", "properties": {}})
    with patch(_OPENAI_CTOR, sdk_class):
        client = OpenAIClient(model=_GPT6_LUNA, api_key="k")
        await client.send_message(
            messages=[_user_msg()],
            temperature=0.2,
            output_format=OutputFormat(tools=(tool,), tool_choice="required"),
        )
    kwargs = create_mock.call_args.kwargs
    assert kwargs["reasoning_effort"] == "none"
    assert kwargs["temperature"] == pytest.approx(0.2)
    assert kwargs["tool_choice"] == "required"


@allure.title("Models that already default to no reasoning are sent without a reasoning_effort field")
@pytest.mark.parametrize("model", ["gpt-5.4-mini", "gpt-4", "deepseek-chat"])
@pytest.mark.asyncio
async def test_other_models_omit_reasoning_effort(model: str) -> None:
    sdk_class, create_mock = _install_sdk_mock()
    with patch(_OPENAI_CTOR, sdk_class):
        client = OpenAIClient(model=model, api_key="k")
        await client.send_message(messages=[_user_msg()])
    assert "reasoning_effort" not in create_mock.call_args.kwargs


@allure.title("Every default role model reaches the OpenAI wire with reasoning_effort pinned to none")
@pytest.mark.parametrize("role_field", _ROLE_MODEL_FIELDS)
@pytest.mark.asyncio
async def test_default_role_model_pins_reasoning_none_on_wire(role_field: str) -> None:
    sdk_class, create_mock = _install_sdk_mock()
    model_config = resolve_model_config(Config.model_fields[role_field].default)
    with patch(_OPENAI_CTOR, sdk_class):
        client = create_llm_client(model_config, api_key="k")
        await client.send_message(messages=[_user_msg()])
    assert create_mock.call_args.kwargs["reasoning_effort"] == "none"
