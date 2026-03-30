"""Tests for BasePerformer.execute — agent-stack tracking and exception safety."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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
    _StackSnapshotPerformer.captured = []
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


# ---------------------------------------------------------------------------
# _send_json tests
# ---------------------------------------------------------------------------


class _JsonPerformer(BasePerformer):
    async def act(self, input_data, context):
        return await self._send_json(input_data)


def _make_json_performer() -> _JsonPerformer:
    return _JsonPerformer(llm_client=MagicMock(), system_prompt_template=PromptTemplate([]))


@pytest.mark.asyncio
async def test_send_json_returns_parsed_dict_on_first_success():
    """_send_json returns a dict immediately when the first response is valid JSON."""
    performer = _make_json_performer()
    with patch.object(performer, "_send", new=AsyncMock(return_value='{"key": "value"}')):
        output = await performer._send_json("prompt")
    assert output == {"key": "value"}


@pytest.mark.asyncio
async def test_send_json_bracket_extraction_fallback():
    """After exhausting retries, _send_json extracts JSON from surrounding text."""
    performer = _make_json_performer()
    # All responses have embedded JSON but surrounded by noise
    with patch.object(performer, "_send", new=AsyncMock(return_value='noise {"extracted": true} noise')):
        extracted = await performer._send_json("prompt", retries=0)
    assert extracted == {"extracted": True}


@pytest.mark.asyncio
async def test_send_json_raises_value_error_when_all_retries_fail():
    """_send_json raises ValueError when every attempt returns non-JSON."""
    performer = _make_json_performer()
    with patch.object(performer, "_send", new=AsyncMock(return_value="not json at all")) as mock_send:
        with pytest.raises(ValueError, match="failed to produce valid JSON"):
            await performer._send_json("prompt", retries=2)
    assert mock_send.call_count == 3


@pytest.mark.asyncio
async def test_send_json_bracket_extraction_invalid_inner_braces():
    """Bracket extraction that finds {…} but inner content is invalid JSON raises ValueError."""
    performer = _make_json_performer()
    with patch.object(performer, "_send", new=AsyncMock(return_value="prefix {broken json} suffix")):
        with pytest.raises(ValueError, match="failed to produce valid JSON"):
            await performer._send_json("prompt", retries=0)


@pytest.mark.asyncio
async def test_send_json_non_json_exception_propagates():
    """Non-JSONDecodeError exceptions must not be swallowed by the bracket-extraction block."""
    performer = _make_json_performer()

    async def _bad_send(*args, **kwargs):
        raise UnicodeDecodeError("utf-8", b"", 0, 1, "reason")

    with patch.object(performer, "_send", new=_bad_send):
        with pytest.raises(UnicodeDecodeError):
            await performer._send_json("prompt", retries=0)
