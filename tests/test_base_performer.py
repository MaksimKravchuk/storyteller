"""Tests for BasePerformer.execute — agent-stack tracking and exception safety."""

from __future__ import annotations

import pytest

from cast.base_performer_class import BasePerformer
from llm.call_logger import reset_buffer
from tests.base_performer_helpers import (
    EMPTY_PROMPT,
    OKPerformer,
    RaisingPerformer,
    StackRecorder,
    get_stack,
    make_mock,
)
from tests.base_performer_nested import ContextCapture, ContextRawCapture, OuterCatcher, OuterDelegator

_INPUT = "input"
_captured_stack: list[str] = []


@pytest.fixture(autouse=True)
def _clean_stack():
    _captured_stack.clear()
    reset_buffer()
    yield
    reset_buffer()


class TestBasePerformerExecuteBasic:
    def test_logging_extracted_from_class(self):
        assert not hasattr(BasePerformer, "_log_llm_call")
        assert not hasattr(BasePerformer, "_capture_call_log")

    @pytest.mark.asyncio
    async def test_returns_act_result(self):
        outcome = await OKPerformer("hello").execute(_INPUT)
        assert outcome == "hello"

    @pytest.mark.asyncio
    async def test_propagates_exception_unchanged(self):
        with pytest.raises(RuntimeError, match="original error"):
            await RaisingPerformer(RuntimeError("original error")).execute(_INPUT)

    @pytest.mark.asyncio
    async def test_pushes_agent_name_during_act(self):
        performer = StackRecorder(target=_captured_stack)
        await performer.execute(_INPUT)
        assert "StackRecorder" in _captured_stack

    @pytest.mark.asyncio
    async def test_pops_agent_name_after_completion(self):
        before = list(get_stack())
        await OKPerformer().execute(_INPUT)
        assert list(get_stack()) == before

    @pytest.mark.asyncio
    async def test_pops_agent_name_when_act_raises(self):
        before = list(get_stack())
        with pytest.raises(ValueError, match="boom"):
            await RaisingPerformer(ValueError("boom")).execute(_INPUT)
        assert list(get_stack()) == before


class TestBasePerformerExecuteNested:
    @pytest.mark.asyncio
    async def test_nested_stack_is_correct(self):
        await OuterDelegator(target=_captured_stack).execute(_INPUT)
        assert "OuterDelegator" in _captured_stack
        assert "StackRecorder" in _captured_stack
        assert _captured_stack.index("OuterDelegator") < _captured_stack.index("StackRecorder")

    @pytest.mark.asyncio
    async def test_nested_stack_restored_after_inner_raises(self):
        """Outer execute's finally must fire correctly even if inner execute raises."""
        before = list(get_stack())
        await OuterCatcher(llm_client=make_mock(), system_prompt_template=EMPTY_PROMPT).execute(_INPUT)
        assert list(get_stack()) == before

    @pytest.mark.asyncio
    async def test_context_passed_to_act(self):
        received = {}
        performer = ContextCapture(received=received)
        await performer.execute(_INPUT, context={"key": "value"})
        assert received == {"key": "value"}

    @pytest.mark.asyncio
    async def test_empty_context_is_empty_dict(self):
        ctx_holder = {}
        await ContextRawCapture(holder=ctx_holder).execute("x")
        assert not ctx_holder["ctx"]
