"""Tests for call chain tracking: execute() wrapper and _send() parent/sequence capture."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from cast.base_performer_class import BasePerformer
from llm.call_logger import (
    agent_stack,
    call_log_buffer,
    current_session_id,
    reset_buffer,
)
from llm.message import LLMResponse
from prompts.base_template import PromptTemplate

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SESSION_ID = "test-session"
_HI = "hi"
_CALL_SEQUENCE = "call_sequence"
_MESSAGE_KEY = "message"


# ---------------------------------------------------------------------------
# Test agent stubs
# ---------------------------------------------------------------------------


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


class AgentA(BasePerformer):
    """Stub agent that calls AgentB inside its act()."""

    def __init__(self, llm_client, child: BasePerformer | None = None):
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=PromptTemplate(),
        )
        self.child = child

    async def act(self, input_data: Any, context: dict) -> Any:
        await self._send("hello from A")
        if self.child:
            await self.child.execute(input_data, context)
        return "done A"


class AgentB(BasePerformer):
    """Stub leaf agent."""

    def __init__(self, llm_client):
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=PromptTemplate(),
        )

    async def act(self, input_data: Any, context: dict) -> Any:
        await self._send("hello from B")
        return "done B"


class FailingAgent(BasePerformer):
    """Agent whose act() raises an error."""

    def __init__(self, llm_client):
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=PromptTemplate(),
        )

    async def act(self, input_data: Any, context: dict) -> Any:
        raise RuntimeError("boom")


def _make_agent_b() -> AgentB:
    return AgentB(llm_client=_mock_llm())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExecuteStackManagement:
    @pytest.mark.asyncio
    async def test_stack_empty_before_and_after(self):
        reset_buffer()
        current_session_id.set(_SESSION_ID)
        agent = _make_agent_b()

        assert agent_stack.get([]) == []
        await agent.execute(_HI)
        assert agent_stack.get([]) == []

    @pytest.mark.asyncio
    async def test_stack_cleaned_on_exception(self):
        reset_buffer()
        current_session_id.set(_SESSION_ID)
        agent = FailingAgent(llm_client=_mock_llm())

        with pytest.raises(RuntimeError, match="boom"):
            await agent.execute(_HI)

        assert agent_stack.get([]) == []


class TestParentAgentTracking:
    @pytest.mark.asyncio
    async def test_root_agent_has_no_parent(self):
        reset_buffer()
        current_session_id.set(_SESSION_ID)
        agent = _make_agent_b()

        await agent.execute(_HI)

        buf = call_log_buffer.get([])
        assert len(buf) == 1
        assert buf[0]["agent_name"] == "AgentB"
        assert buf[0]["parent_agent"] is None

    @pytest.mark.asyncio
    async def test_nested_agent_has_parent(self):
        reset_buffer()
        current_session_id.set(_SESSION_ID)
        child = _make_agent_b()
        parent = AgentA(llm_client=_mock_llm(), child=child)

        await parent.execute(_HI)

        buf = call_log_buffer.get([])
        assert len(buf) == 2

        # First call: AgentA._send() — no parent
        assert buf[0]["agent_name"] == "AgentA"
        assert buf[0]["parent_agent"] is None

        # Second call: AgentB._send() — parent is AgentA
        assert buf[1]["agent_name"] == "AgentB"
        assert buf[1]["parent_agent"] == "AgentA"


class TestLogging:
    @pytest.mark.asyncio
    async def test_send_emits_llm_structured_log(self, loguru_sink):
        """_send() must emit an INFO record with agent, model, tokens, and duration."""
        reset_buffer()
        agent = _make_agent_b()
        await agent.execute(_HI)
        llm_records = [rec for rec in loguru_sink if rec[_MESSAGE_KEY].startswith("LLM |")]
        assert len(llm_records) == 1
        msg = llm_records[0][_MESSAGE_KEY]
        assert "agent=AgentB" in msg
        assert "model=test-model" in msg
        assert "prompt_tokens=10" in msg

    @pytest.mark.asyncio
    async def test_send_log_has_completion_tokens(self, loguru_sink):
        """LLM log must include completion_tokens and duration_ms."""
        reset_buffer()
        agent = _make_agent_b()
        await agent.execute(_HI)
        llm_records = [rec for rec in loguru_sink if rec[_MESSAGE_KEY].startswith("LLM |")]
        msg = llm_records[0][_MESSAGE_KEY]
        assert "completion_tokens=5" in msg
        assert "duration_ms=" in msg

    @pytest.mark.asyncio
    async def test_execute_log_parent_in_nested_call(self, loguru_sink):
        """The child agent's start log must include the parent agent name."""
        reset_buffer()
        child = _make_agent_b()
        parent = AgentA(llm_client=_mock_llm(), child=child)
        await parent.execute(_HI)
        start_records = [rec for rec in loguru_sink if "| start" in rec[_MESSAGE_KEY]]
        child_start = next(rec for rec in start_records if "AgentB" in rec[_MESSAGE_KEY])
        assert "parent=AgentA" in child_start[_MESSAGE_KEY]


class TestCallSequence:
    @pytest.mark.asyncio
    async def test_sequence_increments(self):
        reset_buffer()
        current_session_id.set(_SESSION_ID)
        child = _make_agent_b()
        parent = AgentA(llm_client=_mock_llm(), child=child)

        await parent.execute(_HI)

        buf = call_log_buffer.get([])
        assert buf[0][_CALL_SEQUENCE] == 0
        assert buf[1][_CALL_SEQUENCE] == 1

    @pytest.mark.asyncio
    async def test_sequence_resets_with_buffer(self):
        reset_buffer()
        current_session_id.set(_SESSION_ID)
        agent = _make_agent_b()

        await agent.execute(_HI)
        assert call_log_buffer.get([])[0][_CALL_SEQUENCE] == 0

        reset_buffer()
        current_session_id.set(_SESSION_ID)
        await agent.execute("hi again")
        assert call_log_buffer.get([])[0][_CALL_SEQUENCE] == 0
