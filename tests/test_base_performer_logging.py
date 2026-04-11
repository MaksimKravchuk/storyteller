"""Tests for BasePerformer logging — start/done/error records and _send_json warnings."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from cast.base_performer_class import BasePerformer
from llm.call_logger import reset_buffer
from prompts.base_template import PromptTemplate

_MESSAGE_KEY = "message"
_EMPTY_PROMPT = PromptTemplate([])


class _OKLogging(BasePerformer):
    async def act(self, input_data, context):
        return "hello"


class _RaiserLogging(BasePerformer):
    async def act(self, input_data, context):
        raise ValueError("boom")


class _JsonLogging(BasePerformer):
    async def act(self, input_data, context):
        return await self._send_json(input_data)


@pytest.fixture(autouse=True)
def _clean_logging():
    reset_buffer()
    yield
    reset_buffer()


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("BasePerformer logging")
class TestExecuteLogging:
    @allure.story("Start/done records")
    @allure.title(
        "BasePerformer.execute emits a 'start' log record and a 'done' record with duration_ms on the happy path"
    )
    @pytest.mark.asyncio
    async def test_emits_start_and_done_logs(self, loguru_sink):
        await _OKLogging(llm_client=MagicMock(), system_prompt_template=_EMPTY_PROMPT).execute("input")
        messages = [rec[_MESSAGE_KEY] for rec in loguru_sink]
        has_start = any("| start" in msg and "_OKLogging" in msg for msg in messages)
        done_messages = [msg for msg in messages if "| done" in msg and "_OKLogging" in msg]
        has_done = any("duration_ms=" in msg for msg in done_messages)
        assert has_start
        assert has_done

    @allure.story("Error records")
    @allure.title("BasePerformer.execute emits an ERROR log that captures the exception type, duration, and traceback")
    @pytest.mark.asyncio
    async def test_error_log_has_exc_type(self, loguru_sink):
        with pytest.raises(ValueError):
            await _RaiserLogging(llm_client=MagicMock(), system_prompt_template=_EMPTY_PROMPT).execute("input")
        error_records = [rec for rec in loguru_sink if rec["level"].name == "ERROR"]
        assert len(error_records) == 1
        error_message = error_records[0][_MESSAGE_KEY]
        assert "| error" in error_message
        assert "exc_type=ValueError" in error_message
        assert "duration_ms=" in error_message
        assert error_records[0]["exception"] is not None

    @allure.story("JSON warnings")
    @allure.title(
        "BasePerformer._send_json emits a WARNING per failed attempt plus a final bracket-extraction failure warning"
    )
    @pytest.mark.asyncio
    async def test_send_json_warning_per_attempt(self, loguru_sink):
        performer = _JsonLogging(llm_client=MagicMock(), system_prompt_template=_EMPTY_PROMPT)
        with patch.object(performer, "_send", new=AsyncMock(return_value="not json")):
            with pytest.raises(ValueError):
                await performer._send_json("prompt", retries=1)
        warnings = [rec for rec in loguru_sink if rec["level"].name == "WARNING"]
        assert len(warnings) == 3
        assert "attempt 1/2" in warnings[0][_MESSAGE_KEY]
        assert "attempt 2/2" in warnings[1][_MESSAGE_KEY]
        assert "Bracket extraction also failed" in warnings[2][_MESSAGE_KEY]
