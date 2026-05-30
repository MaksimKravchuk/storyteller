"""Regression: Director records a deterministic ``clock_advance`` turn event.

The admin agent-flow view renders deterministic pipeline nodes from
``turn_events``. Before this, an ordinary EXPLORE/MOVE turn emitted nothing
deterministic (dice/hostility/item events only fire on specific actions), so
the deterministic half of the flow graph was empty. The clock advance happens
every turn, so emitting it as a ``clock_advance`` turn event guarantees the
deterministic lane is always populated. Observation-only, per ADR-0002.
"""

from __future__ import annotations

import allure
import pytest

from llm.call_logger import current_session_id
from llm.turn_event_logger import get_and_clear_events, reset_events
from tests.director_helpers import make_director

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Director orchestration"),
]


@allure.story("Clock-advance telemetry")
@allure.title("_advance_clock_and_tick_background records exactly one clock_advance turn event")
@pytest.mark.asyncio
async def test_clock_advance_emits_turn_event():
    director = make_director()
    current_session_id.set("sess-clock")
    reset_events()
    clock_before = director._game_state.game_clock

    await director._advance_clock_and_tick_background("EXPLORE", None)

    clock_events = [e for e in get_and_clear_events() if e["event_type"] == "clock_advance"]
    assert len(clock_events) == 1
    event = clock_events[0]
    payload = event["payload"]
    assert event["agent_name"] == "Director"
    assert payload["action_type"] == "EXPLORE"
    assert payload["hours"] >= 0
    assert payload["clock_before"] == clock_before
    assert payload["clock_after"] == clock_before + payload["hours"]
    assert payload["completed_events"] == []


@allure.story("Clock-advance telemetry")
@allure.title("clock_advance payload lists the names of events completed by the advance")
@pytest.mark.asyncio
async def test_clock_advance_lists_completed_events():
    director = make_director()
    from timeline.event import GameEvent

    gs = director._game_state
    director.schedule_event(
        GameEvent(name="Guard patrol concludes", scheduled_at=gs.game_clock, duration=0.5),
    )
    current_session_id.set("sess-clock-completed")
    reset_events()

    # WAIT advances the clock far enough to complete the 0.5h event.
    await director._advance_clock_and_tick_background("WAIT", 1.0)

    clock_events = [e for e in get_and_clear_events() if e["event_type"] == "clock_advance"]
    assert len(clock_events) == 1
    assert clock_events[0]["payload"]["completed_events"] == ["Guard patrol concludes"]
