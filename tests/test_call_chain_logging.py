"""Tests for call chain _send() logging: structured LLM log and parent agent in nested calls."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from cast.base_performer_class import BasePerformer
from llm.call_logger import reset_buffer
from llm.message import LLMResponse
from prompts.base_template import PromptTemplate

_HI = "hi"
_MESSAGE_KEY = "message"


def _mock_llm() -> AsyncMock:
    """Create a mock LLM client that returns a valid LLMResponse."""
    client = AsyncMock()
    client.model = "test-model"
    client.send_message = AsyncMock(
        return_value=LLMResponse(
            body="test response",
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )
    )
    return client


class _AgentB(BasePerformer):
    def __init__(self, llm_client):
        super().__init__(llm_client=llm_client, system_prompt_template=PromptTemplate())

    async def act(self, input_data: Any, context: dict) -> Any:
        await self._send("hello from B")
        return "done B"


class _AgentAWithChild(BasePerformer):
    """Agent that delegates to a child agent after sending its own message."""

    def __init__(self, llm_client, child):
        super().__init__(llm_client=llm_client, system_prompt_template=PromptTemplate())
        self.child = child

    async def act(self, input_data, context):
        await self._send("hello from A")
        await self.child.execute(input_data, context)
        return "done A"


class TestCallChainLogging:
    @pytest.mark.asyncio
    async def test_send_emits_llm_structured_log(self, loguru_sink):
        reset_buffer()
        agent = _AgentB(llm_client=_mock_llm())
        await agent.execute(_HI)
        llm_records = [rec for rec in loguru_sink if rec[_MESSAGE_KEY].startswith("LLM |")]
        assert len(llm_records) == 1
        msg = llm_records[0][_MESSAGE_KEY]
        assert "agent=_AgentB" in msg
        assert "model=test-model" in msg
        assert "prompt_tokens=10" in msg

    @pytest.mark.asyncio
    async def test_send_log_has_completion_tokens(self, loguru_sink):
        reset_buffer()
        agent = _AgentB(llm_client=_mock_llm())
        await agent.execute(_HI)
        llm_records = [rec for rec in loguru_sink if rec[_MESSAGE_KEY].startswith("LLM |")]
        msg = llm_records[0][_MESSAGE_KEY]
        assert "completion_tokens=5" in msg
        assert "duration_ms=" in msg

    @pytest.mark.asyncio
    async def test_execute_log_parent_in_nested_call(self, loguru_sink):
        reset_buffer()

        child = _AgentB(llm_client=_mock_llm())
        parent = _AgentAWithChild(llm_client=_mock_llm(), child=child)
        await parent.execute(_HI)
        start_records = [rec for rec in loguru_sink if "| start" in rec[_MESSAGE_KEY]]
        child_start = next(rec for rec in start_records if "_AgentB" in rec[_MESSAGE_KEY])
        assert "parent=_AgentAWithChild" in child_start[_MESSAGE_KEY]
