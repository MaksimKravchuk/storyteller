"""Tests for the turn_event_logger contextvar buffer."""

from __future__ import annotations

import allure

from llm.call_logger import agent_stack, current_session_id
from llm.turn_event_logger import (
    get_and_clear_events,
    record_turn_event,
    reset_events,
    turn_event_buffer,
    turn_event_sequence_counter,
)

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Turn event logger"),
]


_SESSION_ID = "sess-abc"


@allure.story("Buffer reset")
@allure.title("reset_events clears the turn_event_buffer back to an empty list")
def test_reset_clears_buffer():
    turn_event_buffer.set([{"event_type": "dice_contest"}])

    reset_events()

    assert turn_event_buffer.get(None) == []


@allure.story("Buffer reset")
@allure.title("reset_events resets the sequence counter back to zero")
def test_reset_clears_sequence_counter():
    turn_event_sequence_counter.set([7])

    reset_events()

    assert turn_event_sequence_counter.get([0])[0] == 0


@allure.story("Record event")
@allure.title("record_turn_event is a no-op when current_session_id is unset")
def test_record_noop_without_session_id():
    current_session_id.set(None)
    reset_events()

    record_turn_event("dice_contest", {"outcome": "actor_succeeds"})

    assert turn_event_buffer.get(None) == []


@allure.story("Record event")
@allure.title("record_turn_event appends payload, auto-incrementing sequence")
def test_record_appends_entries_with_sequence():
    current_session_id.set(_SESSION_ID)
    reset_events()

    record_turn_event("dice_contest", {"outcome": "actor_succeeds"}, npc_id="npc-1")
    record_turn_event("item_list", {"expanded": ["dagger"]})

    snapshot = get_and_clear_events()
    assert len(snapshot) == 2
    assert snapshot[0]["event_type"] == "dice_contest"
    assert snapshot[0]["npc_id"] == "npc-1"
    assert snapshot[0]["sequence"] == 0
    assert snapshot[1]["event_type"] == "item_list"
    assert snapshot[1]["sequence"] == 1


@allure.story("Record event")
@allure.title("record_turn_event picks up agent_name from the agent_stack top")
def test_record_inherits_agent_from_stack():
    current_session_id.set(_SESSION_ID)
    reset_events()
    agent_stack.set(["Director"])

    record_turn_event("dice_contest", {"outcome": "actor_succeeds"})

    events = get_and_clear_events()
    assert events[0]["agent_name"] == "Director"


@allure.story("Buffer flush")
@allure.title("get_and_clear_events returns entries and empties the buffer")
def test_flush_empties_buffer():
    current_session_id.set(_SESSION_ID)
    reset_events()
    record_turn_event("dice_contest", {"outcome": "actor_succeeds"})

    first = get_and_clear_events()
    second = get_and_clear_events()

    assert len(first) == 1
    assert second == []


@allure.story("Buffer flush")
@allure.title("get_and_clear_events returns [] when buffer was never initialised")
def test_flush_empty_when_never_initialised():
    turn_event_buffer.set(None)

    assert get_and_clear_events() == []
