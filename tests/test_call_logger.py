"""Tests for call_logger context variables including call chain tracking."""

from __future__ import annotations

from llm.call_logger import (
    agent_stack,
    call_log_buffer,
    call_sequence_counter,
    reset_buffer,
)


class TestResetBuffer:
    def test_clears_call_log_buffer(self):
        buf = call_log_buffer.get([])
        buf.append({"agent_name": "Director"})
        call_log_buffer.set(buf)

        reset_buffer()

        assert call_log_buffer.get([]) == []

    def test_clears_agent_stack(self):
        stack = agent_stack.get([])
        stack.append("Director")
        agent_stack.set(stack)

        reset_buffer()

        assert agent_stack.get([]) == []

    def test_clears_sequence_counter(self):
        call_sequence_counter.set(5)

        reset_buffer()

        assert call_sequence_counter.get(0) == 0


class TestAgentStack:
    def test_default_is_empty_list(self):
        reset_buffer()
        assert agent_stack.get([]) == []

    def test_push_and_pop(self):
        reset_buffer()
        stack = agent_stack.get([])
        stack.append("Director")
        agent_stack.set(stack)
        assert agent_stack.get([]) == ["Director"]

        stack.append("Narrator")
        agent_stack.set(stack)
        assert agent_stack.get([]) == ["Director", "Narrator"]

        stack.pop()
        agent_stack.set(stack)
        assert agent_stack.get([]) == ["Director"]


class TestCallSequenceCounter:
    def test_default_is_zero(self):
        reset_buffer()
        assert call_sequence_counter.get(0) == 0

    def test_increment(self):
        reset_buffer()
        current_count = call_sequence_counter.get(0)
        call_sequence_counter.set(current_count + 1)
        assert call_sequence_counter.get(0) == 1
