"""Unit tests for cast.director_events.EventProcessor."""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast.director_events import EventProcessor, _scope_from_string
from knowledge import graph as _kg, node as _kn
from models.game_state import GameState, PlayerState
from models.location import Location
from models.setting import Setting
from tests._uuid_helpers import make_uuid
from timeline.event import GameEvent
from timeline.event_manager import EventManager

KnowledgeGraph = _kg.KnowledgeGraph
KnowledgeScope = _kn.KnowledgeScope


def _make_state() -> GameState:
    tavern_id = make_uuid("tavern")
    gs = GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=KnowledgeGraph(),
        player=PlayerState(location_id=tavern_id),
    )
    gs.locations[tavern_id] = Location(
        name="Tavern",
        npcs_present=[make_uuid("npc-1"), make_uuid("npc-2")],
    )
    return gs


def _make_processor(gs: GameState, memory_mgr: AsyncMock | None = None) -> EventProcessor:
    event_mgr = EventManager(gs, gs.knowledge_graph)
    if memory_mgr is None:
        memory_mgr = AsyncMock()
        memory_mgr.create_memory_from_event = AsyncMock(return_value=[])
    return EventProcessor(gs, event_mgr, memory_mgr)


@allure.epic("Game Timeline")
@allure.feature("Director event processor")
class TestAdvanceAndResolve:
    @allure.story("Time advance")
    @allure.title("advance_and_resolve() delegates to EventManager with the action's time cost")
    def test_advance_delegates_to_event_manager(self):
        gs = _make_state()
        processor = _make_processor(gs)

        events, hours = processor.advance_and_resolve("EXPLORE", time_override=None)

        assert events == []  # no scheduled events
        assert gs.game_clock > 0
        assert hours > 0

    @allure.story("Time advance")
    @allure.title("advance_and_resolve() honors an explicit time override when provided")
    def test_advance_with_override(self):
        gs = _make_state()
        processor = _make_processor(gs)

        _events, hours = processor.advance_and_resolve("EXPLORE", time_override=4.5)

        assert gs.game_clock == pytest.approx(4.5)
        assert hours == pytest.approx(4.5)


@allure.epic("Game Timeline")
@allure.feature("Director event processor")
class TestPartitionEvents:
    @allure.story("Local/remote partition")
    @allure.title("partition_events() groups events by whether they share the player's location")
    def test_splits_local_and_remote(self):
        gs = _make_state()
        processor = _make_processor(gs)
        here = GameEvent(name="Brawl", scheduled_at=0, duration=1, location_id=make_uuid("tavern"))
        there = GameEvent(name="Fire", scheduled_at=0, duration=1, location_id=make_uuid("market"))

        local, remote = processor.partition_events([here, there])

        assert local == [here]
        assert remote == [there]

    @allure.story("Local/remote partition")
    @allure.title("partition_events() treats events with no location as remote")
    def test_events_without_location_are_remote(self):
        gs = _make_state()
        processor = _make_processor(gs)
        floating = GameEvent(name="Omen", scheduled_at=0, duration=1, location_id=None)

        local, remote = processor.partition_events([floating])

        assert local == []
        assert remote == [floating]


@allure.epic("Game Timeline")
@allure.feature("Director event processor")
class TestBuildMemoryKwargs:
    @allure.story("Memory kwargs")
    @allure.title("build_memory_kwargs() uses on_complete_description as the event summary when present")
    def test_uses_on_complete_description(self):
        gs = _make_state()
        processor = _make_processor(gs)
        ev = GameEvent(
            name="Riot",
            scheduled_at=0,
            duration=1,
            scope="city",
            location_id=make_uuid("tavern"),
            on_complete_description="A riot breaks out.",
        )

        kwargs = processor.build_memory_kwargs(ev)

        assert kwargs["event_description"] == "A riot breaks out."
        assert kwargs["scope"] == KnowledgeScope.CITY
        assert kwargs["location_id"] == make_uuid("tavern")
        assert kwargs["witness_ids"] == [make_uuid("npc-1"), make_uuid("npc-2")]

    @allure.story("Memory kwargs")
    @allure.title("build_memory_kwargs() falls back to the event name when no description is set")
    def test_falls_back_to_name(self):
        gs = _make_state()
        processor = _make_processor(gs)
        ev = GameEvent(name="Parade", scheduled_at=0, duration=1, location_id=make_uuid("tavern"))

        kwargs = processor.build_memory_kwargs(ev)

        assert kwargs["event_description"] == "Parade"

    @allure.story("Memory kwargs")
    @allure.title("build_memory_kwargs() returns no witnesses when the location is unknown")
    def test_no_witnesses_when_location_unknown(self):
        gs = _make_state()
        processor = _make_processor(gs)
        ev = GameEvent(name="Comet", scheduled_at=0, duration=1, location_id=make_uuid("unknown"))

        kwargs = processor.build_memory_kwargs(ev)

        assert kwargs["witness_ids"] == []


@allure.epic("Game Timeline")
@allure.feature("Director event processor")
class TestProcessRemoteEvents:
    @allure.story("Remote event memories")
    @pytest.mark.asyncio
    @allure.title("process_remote_events() feeds each event into MemoryManager.create_memory_from_event")
    async def test_creates_memory_for_each_event(self):
        gs = _make_state()
        event_mgr = EventManager(gs, gs.knowledge_graph)
        memory_mgr = AsyncMock()
        memory_mgr.create_memory_from_event = AsyncMock(return_value=[])
        processor = EventProcessor(gs, event_mgr, memory_mgr)

        events = [
            GameEvent(name="A", scheduled_at=0, duration=1, location_id=make_uuid("tavern"), scope="region"),
            GameEvent(name="B", scheduled_at=0, duration=1, location_id=make_uuid("market"), scope="world"),
        ]
        await processor.process_remote_events(events)

        assert memory_mgr.create_memory_from_event.await_count == 2
        # Pin the kwargs flow — a no-op build_memory_kwargs must NOT pass.
        memory_mgr.create_memory_from_event.assert_any_await(
            event_description="A",
            scope=KnowledgeScope.REGION,
            location_id=make_uuid("tavern"),
            witness_ids=[make_uuid("npc-1"), make_uuid("npc-2")],
            game_time=gs.game_clock,
        )
        memory_mgr.create_memory_from_event.assert_any_await(
            event_description="B",
            scope=KnowledgeScope.WORLD,
            location_id=make_uuid("market"),
            witness_ids=[],  # "market" not in gs.locations → no witnesses
            game_time=gs.game_clock,
        )


@allure.epic("Game Timeline")
@allure.feature("Director event processor")
class TestScopeFromString:
    @allure.story("Scope mapping")
    @allure.title("_scope_from_string maps known scope labels to KnowledgeScope enum values")
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("local", KnowledgeScope.LOCAL),
            ("city", KnowledgeScope.CITY),
            ("region", KnowledgeScope.REGION),
            ("country", KnowledgeScope.COUNTRY),
            ("world", KnowledgeScope.WORLD),
        ],
    )
    def test_known_scopes(self, raw, expected):
        assert _scope_from_string(raw) == expected

    @allure.story("Scope mapping")
    @allure.title("_scope_from_string defaults unknown scope labels to LOCAL")
    def test_unknown_scope_defaults_to_local(self):
        assert _scope_from_string("galactic") == KnowledgeScope.LOCAL
