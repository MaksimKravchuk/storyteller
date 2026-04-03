"""Tests for call chain tracking: execute() wrapper and _send() parent/sequence capture."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import asyncio

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


class _ParallelAgent(BasePerformer):
    """Agent that makes one sequential call then N parallel calls via asyncio.gather."""

    def __init__(self, llm_client, num_parallel=5):
        super().__init__(llm_client=llm_client, system_prompt_template=PromptTemplate())
        self._num_parallel = num_parallel

    async def act(self, input_data, context):
        # One sequential call first so the shared buffer is non-empty (truthy).
        await self._send("setup call")
        messages = ["parallel {0}".format(idx) for idx in range(self._num_parallel)]
        coros = [self._send(msg) for msg in messages]
        await asyncio.gather(*coros)
        return "done parallel"


def _init_test_context() -> None:
    """Reset buffer and set test session ID for call-chain tests."""
    reset_buffer()
    current_session_id.set(_SESSION_ID)


class TestExecuteAndParent:
    @pytest.mark.asyncio
    async def test_stack_empty_before_and_after(self):
        _init_test_context()
        agent = _AgentB(llm_client=_mock_llm())
        assert agent_stack.get([]) == []
        await agent.execute(_HI)
        assert agent_stack.get([]) == []

    @pytest.mark.asyncio
    async def test_stack_cleaned_on_exception(self):
        _init_test_context()

        agent = _FailingAgent(llm_client=_mock_llm(), system_prompt_template=PromptTemplate())
        with pytest.raises(RuntimeError, match="boom"):
            await agent.execute(_HI)
        assert agent_stack.get([]) == []

    @pytest.mark.asyncio
    async def test_root_agent_has_no_parent(self):
        _init_test_context()
        await _AgentB(llm_client=_mock_llm()).execute(_HI)
        buf = call_log_buffer.get([])
        assert len(buf) == 1
        assert buf[0]["agent_name"] == "_AgentB"
        assert buf[0]["parent_agent"] is None

    @pytest.mark.asyncio
    async def test_nested_agent_has_parent(self):
        _init_test_context()

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
        _init_test_context()

        child = _AgentB(llm_client=_mock_llm())
        parent = _AgentAWithChild(llm_client=_mock_llm(), child=child)
        await parent.execute(_HI)
        buf = call_log_buffer.get([])
        assert buf[0][_CALL_SEQUENCE] == 0
        assert buf[1][_CALL_SEQUENCE] == 1

    @pytest.mark.asyncio
    async def test_parallel_calls_get_unique_sequences(self):
        """asyncio.gather'd LLM calls must each get a unique call_sequence."""
        _init_test_context()
        agent = _ParallelAgent(llm_client=_mock_llm(), num_parallel=5)
        await agent.execute(_HI)
        buf = call_log_buffer.get([])
        # 1 sequential + 5 parallel = 6 entries
        assert len(buf) == 6, "Expected 6 entries, got {0}".format(len(buf))
        sequences = [entry[_CALL_SEQUENCE] for entry in buf]
        assert len(set(sequences)) == 6, "Expected 6 unique sequences, got {0}".format(sequences)

    @pytest.mark.asyncio
    async def test_consecutive_turns_each_start_at_zero(self):
        """Regression: sequence must restart at 0 for each new turn (reset_buffer)."""
        _init_test_context()
        child = _AgentB(llm_client=_mock_llm())
        parent = _AgentAWithChild(llm_client=_mock_llm(), child=child)
        await parent.execute(_HI)
        buf1 = call_log_buffer.get([])
        assert buf1[0][_CALL_SEQUENCE] == 0

        _init_test_context()
        await parent.execute(_HI)
        buf2 = call_log_buffer.get([])
        assert buf2[0][_CALL_SEQUENCE] == 0, "Turn 2 must restart at 0"
        assert buf2[1][_CALL_SEQUENCE] == 1
