"""Tests for call chain tracking: execute() wrapper and _send() parent/sequence capture."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from cast.base_performer_class import BasePerformer
from llm.call_logger import agent_stack, call_log_buffer, current_session_id, reset_buffer
from llm.message import LLMResponse
from prompts.base_template import PromptTemplate

_SESSION_ID = "test-session"
_HI = "hi"
_CALL_SEQUENCE = "call_sequence"


def _mock_llm() -> AsyncMock:
    """Create a mock LLM client that returns a valid LLMResponse."""
    client = AsyncMock()
    client.model = "test-model"
    client.send_message = AsyncMock(
        return_value=LLMResponse(
            content="test response",
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


class _FailingAgent(BasePerformer):
    """Agent that always raises RuntimeError on act()."""

    async def act(self, input_data, context):
        raise RuntimeError("boom")


class _AgentAWithChild(BasePerformer):
    """Agent that delegates to a child agent after sending its own message."""

    def __init__(self, llm_client, child):
        super().__init__(llm_client=llm_client, system_prompt_template=PromptTemplate())
        self.child = child

    async def act(self, input_data, context):
        await self._send("hello from A")
        await self.child.execute(input_data, context)
        return "done A"


class TestExecuteAndParent:
    @pytest.mark.asyncio
    async def test_stack_empty_before_and_after(self):
        reset_buffer()
        current_session_id.set(_SESSION_ID)
        agent = _AgentB(llm_client=_mock_llm())
        assert agent_stack.get([]) == []
        await agent.execute(_HI)
        assert agent_stack.get([]) == []

    @pytest.mark.asyncio
    async def test_stack_cleaned_on_exception(self):
        reset_buffer()
        current_session_id.set(_SESSION_ID)

        agent = _FailingAgent(llm_client=_mock_llm(), system_prompt_template=PromptTemplate())
        with pytest.raises(RuntimeError, match="boom"):
            await agent.execute(_HI)
        assert agent_stack.get([]) == []

    @pytest.mark.asyncio
    async def test_root_agent_has_no_parent(self):
        reset_buffer()
        current_session_id.set(_SESSION_ID)
        await _AgentB(llm_client=_mock_llm()).execute(_HI)
        buf = call_log_buffer.get([])
        assert len(buf) == 1
        assert buf[0]["agent_name"] == "_AgentB"
        assert buf[0]["parent_agent"] is None

    @pytest.mark.asyncio
    async def test_nested_agent_has_parent(self):
        reset_buffer()
        current_session_id.set(_SESSION_ID)

        child = _AgentB(llm_client=_mock_llm())
        parent = _AgentAWithChild(llm_client=_mock_llm(), child=child)
        await parent.execute(_HI)
        buf = call_log_buffer.get([])
        assert len(buf) == 2
        assert buf[0]["agent_name"] == "_AgentAWithChild"
        assert buf[0]["parent_agent"] is None
        assert buf[1]["agent_name"] == "_AgentB"
        assert buf[1]["parent_agent"] == "_AgentAWithChild"

    @pytest.mark.asyncio
    async def test_sequence_increments(self):
        reset_buffer()
        current_session_id.set(_SESSION_ID)

        child = _AgentB(llm_client=_mock_llm())
        parent = _AgentAWithChild(llm_client=_mock_llm(), child=child)
        await parent.execute(_HI)
        buf = call_log_buffer.get([])
        assert buf[0][_CALL_SEQUENCE] == 0
        assert buf[1][_CALL_SEQUENCE] == 1

    @pytest.mark.asyncio
    async def test_sequence_resets_with_buffer(self):
        reset_buffer()
        current_session_id.set(_SESSION_ID)
        agent = _AgentB(llm_client=_mock_llm())
        await agent.execute(_HI)
        assert call_log_buffer.get([])[0][_CALL_SEQUENCE] == 0
        reset_buffer()
        current_session_id.set(_SESSION_ID)
        await agent.execute("hi again")
        assert call_log_buffer.get([])[0][_CALL_SEQUENCE] == 0
