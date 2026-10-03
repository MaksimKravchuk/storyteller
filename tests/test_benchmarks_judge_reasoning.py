"""Consumer-seam tests: reasoning-only judges reach the provider SDK with a valid request."""

from __future__ import annotations

from unittest.mock import patch

import allure
import pytest

from benchmarks.harness.judge import JudgeCall, _send_judge_prompt
from benchmarks.harness.types._elements import EvidencePromptSpec
from benchmarks.harness.types._scores import PanelMember
from config import Config
from tests.test_anthropic_client import _ANTHROPIC_CTOR
from tests.test_anthropic_client import _install_sdk_mock as _install_anthropic_mock
from tests.test_openai_client import _OPENAI_CTOR
from tests.test_openai_client import _install_sdk_mock as _install_openai_mock

_MIN_REASONING_HEADROOM = 4096

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Benchmark harness"),
    allure.story("Reasoning judges"),
]


def _judge_call() -> JudgeCall:
    spec = EvidencePromptSpec(scenario_brief="b", question="q", evidence_turn=0)
    return JudgeCall(spec=spec, turn_text="turn text")


def _cfg() -> Config:
    return Config(openai_api_key="sk-test", anthropic_api_key="sk-ant-test")


@allure.title("A GPT-6.1 Sol judge call sends low reasoning, no temperature, and room for reasoning tokens")
@pytest.mark.asyncio
async def test_sol_judge_request_is_valid_for_a_reasoning_model() -> None:
    sdk_class, create_mock = _install_openai_mock()
    with patch(_OPENAI_CTOR, sdk_class):
        await _send_judge_prompt(PanelMember(provider="openai", model_id="gpt-6.1-sol"), _judge_call(), _cfg(), 0)
    kwargs = create_mock.call_args.kwargs
    assert kwargs["reasoning_effort"] == "low"
    assert "temperature" not in kwargs
    assert kwargs["max_completion_tokens"] >= _MIN_REASONING_HEADROOM


@allure.title("A Claude Opus 5.5 judge call sends low effort, no temperature, and room for thinking tokens")
@pytest.mark.asyncio
async def test_opus_judge_request_is_valid_for_a_thinking_model() -> None:
    sdk_class, create_mock = _install_anthropic_mock()
    with patch(_ANTHROPIC_CTOR, sdk_class):
        await _send_judge_prompt(
            PanelMember(provider="anthropic", model_id="claude-opus-5-5"), _judge_call(), _cfg(), 0
        )
    kwargs = create_mock.call_args.kwargs
    assert kwargs["output_config"] == {"effort": "low"}
    assert "temperature" not in kwargs
    assert kwargs["max_tokens"] >= _MIN_REASONING_HEADROOM
