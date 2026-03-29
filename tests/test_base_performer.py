"""Tests for BasePerformer.execute — agent-stack tracking and exception safety."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cast.base_performer_class import BasePerformer
from llm.call_logger import agent_stack, reset_buffer
from prompts.base_template import PromptTemplate


# ---------------------------------------------------------------------------
# Minimal concrete performer for testing
# ---------------------------------------------------------------------------


class _OKPerformer(BasePerformer):
    def __init__(self, act_output: str = "ok"):
        super().__init__(llm_client=MagicMock(), system_prompt_template=PromptTemplate([]))
        self._act_output = act_output

    async def act(self, input_data, context):
        return self._act_output


class _RaisingPerformer(BasePerformer):
    def __init__(self, exc: Exception):
        super().__init__(llm_client=MagicMock(), system_prompt_template=PromptTemplate([]))
        self._exc = exc

    async def act(self, input_data, context):
        raise self._exc


class _StackSnapshotPerformer(BasePerformer):
    """Captures the agent stack at act() time for inspection."""

    captured: list[str] = []

    def __init__(self):
        super().__init__(llm_client=MagicMock(), system_prompt_template=PromptTemplate([]))

    async def act(self, input_data, context):
        _StackSnapshotPerformer.captured = list(agent_stack.get(None) or [])
        return "captured"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_stack():
    """Reset the agent stack before each test."""
    reset_buffer()
    yield
    reset_buffer()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_returns_act_result():
    outcome = await _OKPerformer("hello").execute("input")
    assert outcome == "hello"


@pytest.mark.asyncio
async def test_execute_pushes_agent_name_during_act():
    performer = _StackSnapshotPerformer()
    await performer.execute("input")
    assert "_StackSnapshotPerformer" in _StackSnapshotPerformer.captured


@pytest.mark.asyncio
async def test_execute_pops_agent_name_after_completion():
    before = list(agent_stack.get(None) or [])
    await _OKPerformer().execute("input")
    after = list(agent_stack.get(None) or [])
    assert after == before


@pytest.mark.asyncio
async def test_execute_pops_agent_name_when_act_raises():
    """Stack must be restored even if act() raises — no IndexError masking."""
    before = list(agent_stack.get(None) or [])
    with pytest.raises(ValueError, match="boom"):
        await _RaisingPerformer(ValueError("boom")).execute("input")
    after = list(agent_stack.get(None) or [])
    assert after == before


@pytest.mark.asyncio
async def test_execute_propagates_exception_unchanged():
    exc = RuntimeError("original error")
    with pytest.raises(RuntimeError, match="original error"):
        await _RaisingPerformer(exc).execute("input")


@pytest.mark.asyncio
async def test_execute_nested_stack_is_correct():
    """Outer performer should be in the stack when inner performer's act runs."""
    inner = _StackSnapshotPerformer()

    class _OuterPerformer(BasePerformer):
        async def act(self, input_data, context):
            return await inner.execute(input_data)

    outer = _OuterPerformer(llm_client=MagicMock(), system_prompt_template=PromptTemplate([]))
    await outer.execute("input")

    stack = _StackSnapshotPerformer.captured
    assert "_OuterPerformer" in stack
    assert "_StackSnapshotPerformer" in stack
    assert stack.index("_OuterPerformer") < stack.index("_StackSnapshotPerformer")


@pytest.mark.asyncio
async def test_execute_nested_stack_restored_after_inner_raises():
    """Outer execute's finally must fire correctly even if inner execute raises."""

    class _InnerRaiser(BasePerformer):
        async def act(self, input_data, context):
            raise ValueError("inner boom")

    class _OuterCatcher(BasePerformer):
        async def act(self, input_data, context):
            try:
                await _InnerRaiser(llm_client=MagicMock(), system_prompt_template=PromptTemplate([])).execute(
                    input_data
                )
            except ValueError:
                return None  # swallow inner error
            return "unexpected"

    outer = _OuterCatcher(llm_client=MagicMock(), system_prompt_template=PromptTemplate([]))
    before = list(agent_stack.get(None) or [])
    await outer.execute("input")
    after = list(agent_stack.get(None) or [])

    assert after == before


@pytest.mark.asyncio
async def test_execute_context_passed_to_act():
    """execute() must pass context through to act()."""
    received = {}

    class _ContextCapture(BasePerformer):
        async def act(self, input_data, context):
            received.update(context)
            return "ok"

    performer = _ContextCapture(llm_client=MagicMock(), system_prompt_template=PromptTemplate([]))
    await performer.execute("input", context={"key": "value"})
    assert received == {"key": "value"}


@pytest.mark.asyncio
async def test_execute_empty_context_defaults_to_empty_dict():
    """None context becomes {} when passed to act()."""
    received_ctx = {}

    class _ContextCapture(BasePerformer):
        async def act(self, input_data, context):
            received_ctx["ctx"] = context
            return "ok"

    await _ContextCapture(llm_client=MagicMock(), system_prompt_template=PromptTemplate([])).execute("x")
    assert received_ctx["ctx"] == {}
