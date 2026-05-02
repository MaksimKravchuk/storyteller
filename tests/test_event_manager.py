"""Unit tests for EventManager timeline operations."""

from __future__ import annotations

import allure

from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.npc_card import NPCCard
from models.setting import Setting
from tests._uuid_helpers import make_uuid
from timeline.event import EventEffect, EventStatus, GameEvent
from timeline.event_manager import EventManager


def _make_state(npc: NPCCard | None = None) -> GameState:
    gs = GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=KnowledgeGraph(),
    )
    if npc is not None:
        gs.npcs[npc.uuid] = npc
    return gs


@allure.epic("Game Timeline")
@allure.feature("EventManager scheduling")
class TestEventManagerSchedule:
    @allure.story("Schedule and cancel")
    @allure.title("schedule() appends an event and returns its UUID")
    def test_schedule_returns_uuid(self):
        gs = _make_state()
        mgr = EventManager(gs, gs.knowledge_graph)
        event = GameEvent(name="Parade", scheduled_at=0, duration=2)

        returned = mgr.schedule(event)

        assert returned == event.uuid
        assert event in mgr.all_events

    @allure.story("Schedule and cancel")
    @allure.title("all_events setter restores the event list from persistence")
    def test_all_events_setter_restores(self):
        gs = _make_state()
        mgr = EventManager(gs, gs.knowledge_graph)
        restored = [
            GameEvent(name="E1", scheduled_at=0, duration=1),
            GameEvent(name="E2", scheduled_at=1.0, duration=1),
        ]

        mgr.all_events = restored

        assert mgr.all_events == restored
        # Returned list must be a copy — mutations should not leak.
        mgr.all_events.append(GameEvent(name="E3", scheduled_at=2.0, duration=1))
        assert len(mgr.all_events) == 2

    @allure.story("Schedule and cancel")
    @allure.title("cancel() marks a pending event as CANCELLED and returns True")
    def test_cancel_pending_event(self):
        gs = _make_state()
        mgr = EventManager(gs, gs.knowledge_graph)
        event = GameEvent(name="Raid", scheduled_at=0, duration=5)
        mgr.schedule(event)

        assert mgr.cancel(event.uuid) is True
        assert event.status == EventStatus.CANCELLED

    @allure.story("Schedule and cancel")
    @allure.title("cancel() returns False for an unknown event UUID")
    def test_cancel_unknown_event(self):
        gs = _make_state()
        mgr = EventManager(gs, gs.knowledge_graph)

        assert mgr.cancel("nonexistent") is False

    @allure.story("Schedule and cancel")
    @allure.title("cancel() will not re-cancel an already-cancelled event")
    def test_cancel_already_cancelled_event(self):
        gs = _make_state()
        mgr = EventManager(gs, gs.knowledge_graph)
        event = GameEvent(name="Raid", scheduled_at=0, duration=5)
        mgr.schedule(event)
        mgr.cancel(event.uuid)

        assert mgr.cancel(event.uuid) is False


@allure.epic("Game Timeline")
@allure.feature("EventManager query")
class TestEventManagerPendingEvents:
    @allure.story("Pending event queries")
    @allure.title("get_pending_events() returns all pending events when no owner filter is given")
    def test_get_all_pending(self):
        gs = _make_state()
        mgr = EventManager(gs, gs.knowledge_graph)
        e1 = GameEvent(name="E1", scheduled_at=0, duration=1, owner_id=make_uuid("alice"))
        e2 = GameEvent(name="E2", scheduled_at=0, duration=1, owner_id=make_uuid("bob"))
        mgr.schedule(e1)
        mgr.schedule(e2)

        pending = mgr.get_pending_events()

        assert len(pending) == 2
        assert e1 in pending
        assert e2 in pending

    @allure.story("Pending event queries")
    @allure.title("get_pending_events() excludes cancelled events")
    def test_get_pending_excludes_cancelled(self):
        gs = _make_state()
        mgr = EventManager(gs, gs.knowledge_graph)
        e1 = GameEvent(name="E1", scheduled_at=0, duration=1)
        mgr.schedule(e1)
        mgr.cancel(e1.uuid)

        assert mgr.get_pending_events() == []


@allure.epic("Game Timeline")
@allure.feature("EventManager advance")
class TestAdvanceTime:
    @allure.story("Scheduled effects")
    @allure.title("advance_time() applies CHANGE_STATUS effects from completed events")
    def test_advance_applies_effects(self):
        npc = NPCCard(name="Guard", occupation="guard", physical_status="wounded")
        gs = _make_state(npc)
        mgr = EventManager(gs, gs.knowledge_graph)
        event = GameEvent(
            name="Healing",
            scheduled_at=0,
            duration=1,
            effects=[
                EventEffect(
                    effect_type="CHANGE_STATUS",
                    target_id=npc.uuid,
                    effect_data={"npc_id": npc.uuid, "status": "healthy"},
                ),
            ],
        )
        mgr.schedule(event)

        completed = mgr.advance_time(2.0)

        assert completed == [event]
        assert event.status == EventStatus.COMPLETED
        assert npc.physical_status == "healthy"

    @allure.story("Scheduled effects")
    @allure.title("advance_time() returns no events when nothing is scheduled")
    def test_advance_time_with_no_events(self):
        gs = _make_state()
        mgr = EventManager(gs, gs.knowledge_graph)

        assert mgr.advance_time(5.0) == []

    @allure.story("Scheduled effects")
    @allure.title("advance_time() fires an event whose completes_at equals the post-advance clock")
    def test_advance_time_inclusive_upper_bound(self):
        # Pins the <= clock_after half of _collect_completed's window.
        gs = _make_state()
        mgr = EventManager(gs, gs.knowledge_graph)
        event = GameEvent(name="Bell", scheduled_at=0, duration=2)
        mgr.schedule(event)

        completed = mgr.advance_time(2.0)

        assert completed == [event]
        assert event.status == EventStatus.COMPLETED

    @allure.story("Scheduled effects")
    @allure.title("advance_time() does not re-fire an event whose completes_at equals clock_before")
    def test_advance_time_exclusive_lower_bound(self):
        # Pins the > clock_before half of _collect_completed's window.
        gs = _make_state()
        mgr = EventManager(gs, gs.knowledge_graph)
        event = GameEvent(name="Bell", scheduled_at=0, duration=2)
        mgr.schedule(event)
        mgr.advance_time(2.0)  # fires it, clock is now 2.0

        # completes_at (2.0) now equals clock_before (2.0) — must NOT refire.
        completed = mgr.advance_time(1.0)

        assert completed == []
