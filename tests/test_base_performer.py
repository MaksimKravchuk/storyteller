"""Tests for BasePerformer.execute — agent-stack tracking and exception safety."""

from __future__ import annotations

import allure
import pytest

from cast._performer_retry import _strip_markdown_fence
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


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("BasePerformer execution")
class TestBasePerformerExecuteBasic:
    @allure.story("Execute wrapper")
    @allure.title("Logging helpers _log_llm_call and _capture_call_log have been moved out of BasePerformer")
    def test_logging_extracted_from_class(self):
        assert not hasattr(BasePerformer, "_log_llm_call")
        assert not hasattr(BasePerformer, "_capture_call_log")

    @allure.story("Execute wrapper")
    @allure.title("BasePerformer.execute returns the value that the subclass's act() returns")
    @pytest.mark.asyncio
    async def test_returns_act_result(self):
        outcome = await OKPerformer("hello").execute(_INPUT)
        assert outcome == "hello"

    @allure.story("Exception safety")
    @allure.title("Exceptions raised inside act() propagate out of execute() unchanged")
    @pytest.mark.asyncio
    async def test_propagates_exception_unchanged(self):
        with pytest.raises(RuntimeError, match="original error"):
            await RaisingPerformer(RuntimeError("original error")).execute(_INPUT)

    @allure.story("Agent stack tracking")
    @allure.title("BasePerformer.execute pushes the subclass name onto the agent stack while act() runs")
    @pytest.mark.asyncio
    async def test_pushes_agent_name_during_act(self):
        performer = StackRecorder(target=_captured_stack)
        await performer.execute(_INPUT)
        assert "StackRecorder" in _captured_stack

    @allure.story("Agent stack tracking")
    @allure.title("BasePerformer.execute pops its agent name off the stack after act() completes")
    @pytest.mark.asyncio
    async def test_pops_agent_name_after_completion(self):
        before = list(get_stack())
        await OKPerformer().execute(_INPUT)
        assert list(get_stack()) == before

    @allure.story("Exception safety")
    @allure.title("BasePerformer.execute pops its agent name off the stack even when act() raises")
    @pytest.mark.asyncio
    async def test_pops_agent_name_when_act_raises(self):
        before = list(get_stack())
        with pytest.raises(ValueError, match="boom"):
            await RaisingPerformer(ValueError("boom")).execute(_INPUT)
        assert list(get_stack()) == before


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("BasePerformer execution")
class TestBasePerformerExecuteNested:
    @allure.story("Nested execution")
    @allure.title("When an outer performer delegates to an inner one, both names appear on the agent stack in order")
    @pytest.mark.asyncio
    async def test_nested_stack_is_correct(self):
        await OuterDelegator(target=_captured_stack).execute(_INPUT)
        assert "OuterDelegator" in _captured_stack
        assert "StackRecorder" in _captured_stack
        assert _captured_stack.index("OuterDelegator") < _captured_stack.index("StackRecorder")

    @allure.story("Exception safety")
    @allure.title("An outer execute()'s finally block restores the agent stack even if the inner execute() raises")
    @pytest.mark.asyncio
    async def test_nested_stack_restored_after_inner_raises(self):
        """Outer execute's finally must fire correctly even if inner execute raises."""
        before = list(get_stack())
        await OuterCatcher(llm_client=make_mock(), system_prompt_template=EMPTY_PROMPT).execute(_INPUT)
        assert list(get_stack()) == before

    @allure.story("Context propagation")
    @allure.title("BasePerformer.execute forwards the caller-supplied context dict into act()")
    @pytest.mark.asyncio
    async def test_context_passed_to_act(self):
        received = {}
        performer = ContextCapture(received=received)
        await performer.execute(_INPUT, context={"key": "value"})
        assert received == {"key": "value"}

    @allure.story("Context propagation")
    @allure.title("BasePerformer.execute defaults the context passed to act() to an empty dict when none is provided")
    @pytest.mark.asyncio
    async def test_empty_context_is_empty_dict(self):
        ctx_holder = {}
        await ContextRawCapture(holder=ctx_holder).execute("x")
        assert not ctx_holder["ctx"]


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("BasePerformer JSON send")
class TestStripMarkdownFence:
    @allure.story("Markdown fence stripping")
    @allure.title("_strip_markdown_fence returns bare JSON unchanged")
    def test_bare_json_unchanged(self):
        assert _strip_markdown_fence('{"key": "value"}') == '{"key": "value"}'

    @allure.story("Markdown fence stripping")
    @allure.title("_strip_markdown_fence strips ```json fences")
    def test_strips_json_fenced(self):
        result = _strip_markdown_fence('```json\n{"key": "value"}\n```')
        assert result == '{"key": "value"}'

    @allure.story("Markdown fence stripping")
    @allure.title("_strip_markdown_fence strips plain fences without language tag")
    def test_strips_plain_fence(self):
        result = _strip_markdown_fence('```\n{"key": "value"}\n```')
        assert result == '{"key": "value"}'

    @allure.story("Markdown fence stripping")
    @allure.title("_strip_markdown_fence strips leading and trailing whitespace")
    def test_strips_whitespace(self):
        result = _strip_markdown_fence('  {"key": "value"}  ')
        assert result == '{"key": "value"}'

    @allure.story("Markdown fence stripping")
    @allure.title("_strip_markdown_fence returns prose as-is when no fence is present")
    def test_prose_returned_as_is(self):
        assert _strip_markdown_fence("not json at all") == "not json at all"

    @allure.story("Markdown fence stripping")
    @allure.title("_strip_markdown_fence strips uppercase ```JSON fences without including the tag in the content")
    def test_strips_uppercase_json_tag(self):
        result = _strip_markdown_fence('```JSON\n{"key": "value"}\n```')
        assert result == '{"key": "value"}'

    @allure.story("Markdown fence stripping")
    @allure.title("_strip_markdown_fence strips fences even with trailing text after closing ```")
    def test_strips_fence_with_trailing_text(self):
        raw = '```json\n{"key": "value"}\n```\nNote: here you go.'
        result = _strip_markdown_fence(raw)
        assert result == '{"key": "value"}'
