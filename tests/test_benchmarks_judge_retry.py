"""Retry and reliability-metering tests for :mod:`benchmarks.harness.judge`."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import allure
import pytest

from benchmarks.harness.judge import JudgeCall, run_judge
from benchmarks.harness.types._elements import EvidencePromptSpec
from benchmarks.harness.types._scores import PanelMember
from cast._reliability_metrics import reset_counters, snapshot_counters
from config import Config


def _panel_member() -> PanelMember:
    return PanelMember(provider="openai", model_id="gpt-5.4-mini")


def _judge_call(turn_text: str = "a long turn text with the stolen wheat loaf in it") -> JudgeCall:
    spec = EvidencePromptSpec(scenario_brief="b", question="q", evidence_turn=0)
    return JudgeCall(spec=spec, turn_text=turn_text)


def _cfg() -> Config:
    return Config(openai_api_key="sk-test", anthropic_api_key=None)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestJudgeRetry:
    @allure.story("Judge retry")
    @allure.title("run_judge succeeds when first attempt fails but retry returns valid JSON")
    @pytest.mark.asyncio
    async def test_retry_succeeds_on_second_attempt(self):
        good_body = '{"verdict": "YES", "reasoning": "found it", "quote": "stolen wheat loaf"}'
        mock = AsyncMock(side_effect=["not json at all", good_body])
        reset_counters()
        with patch("benchmarks.harness.judge._send_judge_prompt", new=mock):
            vote = await run_judge(_panel_member(), _judge_call(), cfg=_cfg())

        assert vote.verdict == "YES"
        assert vote.error is None
        assert mock.call_count == 2
        counts = snapshot_counters()
        assert counts.get(("gpt-5.4-mini", "judge_error"), 0) == 1

    @allure.story("Judge retry")
    @allure.title("run_judge records judge_error twice when both attempts produce malformed JSON")
    @pytest.mark.asyncio
    async def test_both_attempts_malformed_records_two_errors(self):
        mock = AsyncMock(return_value="not json")
        reset_counters()
        with patch("benchmarks.harness.judge._send_judge_prompt", new=mock):
            vote = await run_judge(_panel_member(), _judge_call(), cfg=_cfg())

        assert vote.verdict == "ERROR"
        assert mock.call_count == 2
        counts = snapshot_counters()
        assert counts.get(("gpt-5.4-mini", "judge_error"), 0) == 2

    @allure.story("Judge retry")
    @allure.title("run_judge happy path calls prompt once and records no judge errors")
    @pytest.mark.asyncio
    async def test_happy_path_no_retry_no_error_recorded(self):
        body = '{"verdict": "NO", "reasoning": "not found", "quote": ""}'
        mock = AsyncMock(return_value=body)
        reset_counters()
        with patch("benchmarks.harness.judge._send_judge_prompt", new=mock):
            vote = await run_judge(_panel_member(), _judge_call(), cfg=_cfg())

        assert vote.verdict == "NO"
        assert mock.call_count == 1
        counts = snapshot_counters()
        assert counts.get(("gpt-5.4-mini", "judge_error"), 0) == 0
