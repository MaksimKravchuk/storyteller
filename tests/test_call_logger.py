"""Tests for call_logger context variables including call chain tracking."""

from __future__ import annotations

import allure

from llm.call_logger import (
    agent_stack,
    call_log_buffer,
    call_sequence_counter,
    get_and_clear_buffer,
    next_sequence,
    reset_buffer,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_AGENT_NAME = "agent_name"
_DIRECTOR = "Director"


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Call logger context")
class TestResetBuffer:
    @allure.story("Buffer reset")
    @allure.title("reset_buffer clears the accumulated call_log_buffer back to an empty list")
    def test_clears_call_log_buffer(self):
        buf = call_log_buffer.get([])
        buf.append({_AGENT_NAME: _DIRECTOR})
        call_log_buffer.set(buf)

        reset_buffer()

        assert call_log_buffer.get([]) == []

    @allure.story("Buffer reset")
    @allure.title("reset_buffer clears the agent_stack context variable back to empty")
    def test_clears_agent_stack(self):
        stack = agent_stack.get([])
        stack.append(_DIRECTOR)
        agent_stack.set(stack)

        reset_buffer()

        assert agent_stack.get([]) == []

    @allure.story("Buffer reset")
    @allure.title("reset_buffer clears the call_sequence_counter back to zero")
    def test_clears_sequence_counter(self):
        call_sequence_counter.set([5])

        reset_buffer()

        assert call_sequence_counter.get([0])[0] == 0


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Call logger context")
class TestAgentStack:
    @allure.story("Agent stack context")
    @allure.title("After reset_buffer the agent_stack context variable defaults to an empty list")
    def test_default_is_empty_list(self):
        reset_buffer()
        assert agent_stack.get([]) == []

    @allure.story("Agent stack context")
    @allure.title("agent_stack supports push and pop of nested agent names as a plain stack")
    def test_push_and_pop(self):
        reset_buffer()
        stack = agent_stack.get([])
        stack.append(_DIRECTOR)
        agent_stack.set(stack)
        assert agent_stack.get([]) == [_DIRECTOR]

        stack.append("Narrator")
        agent_stack.set(stack)
        assert agent_stack.get([]) == [_DIRECTOR, "Narrator"]

        stack.pop()
        agent_stack.set(stack)
        assert agent_stack.get([]) == [_DIRECTOR]


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Call logger context")
class TestCallSequenceCounter:
    @allure.story("Sequence counter")
    @allure.title("call_sequence_counter defaults to zero after reset_buffer")
    def test_default_is_zero(self):
        reset_buffer()
        assert call_sequence_counter.get([0])[0] == 0

    @allure.story("Sequence counter")
    @allure.title("next_sequence returns the counter value then increments it, producing 0, 1, 2 on successive calls")
    def test_next_sequence_increments(self):
        reset_buffer()
        assert next_sequence() == 0
        assert next_sequence() == 1
        assert next_sequence() == 2

    @allure.story("Sequence counter")
    @allure.title("init_sequence(n) seeds the counter so that the next next_sequence returns n and then n+1")
    def test_init_sequence_continues_from_offset(self):
        """After init_sequence(n), next_sequence returns n, n+1, etc."""
        from llm.call_logger import init_sequence

        reset_buffer()
        init_sequence(7)
        assert next_sequence() == 7
        assert next_sequence() == 8


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Call logger context")
class TestGetAndClearBuffer:
    @allure.story("Buffer reset")
    @allure.title("get_and_clear_buffer returns an empty list (not None) when the call buffer was never initialised")
    def test_returns_empty_when_not_initialized(self):
        """get_and_clear_buffer() returns [] (not None) when reset_buffer was never called."""
        call_log_buffer.set(None)
        assert get_and_clear_buffer() == []

    @allure.story("Buffer reset")
    @allure.title("get_and_clear_buffer returns all entries accumulated since the last reset")
    def test_returns_accumulated_entries_and_clears(self):
        """Returns entries written after reset_buffer(), then clears on next call."""
        reset_buffer()
        entries = [{_AGENT_NAME: _DIRECTOR}, {_AGENT_NAME: "Narrator"}]
        call_log_buffer.set(entries)

        snapshot = get_and_clear_buffer()
        assert snapshot == entries

    @allure.story("Buffer reset")
    @allure.title("A second get_and_clear_buffer call returns an empty list because the first call cleared the buffer")
    def test_second_call_returns_empty(self):
        """Buffer is cleared after the first get_and_clear_buffer() call."""
        reset_buffer()
        call_log_buffer.set([{_AGENT_NAME: _DIRECTOR}])

        get_and_clear_buffer()
        second = get_and_clear_buffer()
        assert second == []

    @allure.story("Buffer reset")
    @allure.title("Mutating the list returned by get_and_clear_buffer does not bleed back into the shared buffer")
    def test_returned_list_is_a_copy(self):
        """Mutating the returned list must not affect the buffer on the next call."""
        reset_buffer()
        call_log_buffer.set([{_AGENT_NAME: _DIRECTOR}])

        snapshot = get_and_clear_buffer()
        snapshot.append({_AGENT_NAME: "Intruder"})  # mutate the returned copy

        second = get_and_clear_buffer()
        assert second == []
