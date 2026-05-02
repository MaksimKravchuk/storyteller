"""Tests for the WorldState data model and its converter bridge.

These cover the pure data plumbing for the World Chronicler agent:
default factories, value defaults on WorldThread, the JSONB round-trip
via :mod:`db.converters.world_state`, and the
``GameState.world_state`` default-factory independence guarantee.
"""

from __future__ import annotations

import allure

from db.converters import world_state as conv_world_state
from models.game_state import GameState
from models.world_state import WorldState, WorldThread
from tests._uuid_helpers import make_uuid


@allure.epic("Memory & Persistence")
@allure.feature("WorldState model")
class TestWorldStateDefaults:
    @allure.story("Defaults")
    @allure.title("A new WorldState starts with no threads, no world_mood, and last_chronicled_scene=0")
    def test_default_values(self):
        state = WorldState()
        assert state.threads == []
        assert state.world_mood is None
        assert state.last_chronicled_scene == 0


@allure.epic("Memory & Persistence")
@allure.feature("WorldState model")
class TestWorldThreadDefaults:
    @allure.story("Defaults")
    @allure.title("A new WorldThread with description+category+introduced_scene defaults status to 'open'")
    def test_status_default_open(self):
        thread = WorldThread(
            description="Grain shipments delayed",
            category="economic",
            introduced_scene=2,
        )
        assert thread.description == "Grain shipments delayed"
        assert thread.category == "economic"
        assert thread.introduced_scene == 2
        assert thread.status == "open"
        assert thread.involved_locations == []
        assert thread.involved_npcs == []
        assert thread.last_advanced_scene == 0

    @allure.story("Defaults")
    @allure.title("WorldThread.involved_locations is independent across instances thanks to default_factory")
    def test_involved_locations_independent_per_instance(self):
        thread_a = WorldThread(description="A", category="political", introduced_scene=1)
        thread_b = WorldThread(description="B", category="personal", introduced_scene=2)
        thread_a.involved_locations.append("loc-1")
        assert thread_b.involved_locations == []

    @allure.story("Defaults")
    @allure.title("A WorldThread receives its own UUID from BaseModel separate from any other thread")
    def test_each_thread_has_independent_uuid(self):
        thread_a = WorldThread(description="A", category="social", introduced_scene=1)
        thread_b = WorldThread(description="B", category="natural", introduced_scene=2)
        assert thread_a.uuid != thread_b.uuid


@allure.epic("Memory & Persistence")
@allure.feature("WorldState model")
class TestGameStateWorldStateField:
    @allure.story("GameState plumbing")
    @allure.title("GameState exposes a world_state field that defaults to an empty WorldState")
    def test_default_world_state(self, game_state):
        assert isinstance(game_state.world_state, WorldState)
        assert game_state.world_state.threads == []
        assert game_state.world_state.world_mood is None
        assert game_state.world_state.last_chronicled_scene == 0

    @allure.story("GameState plumbing")
    @allure.title("Two GameState instances each receive their own independent WorldState object")
    def test_default_factory_isolates_instances(self, simple_setting, populated_graph, empty_graph):
        first = GameState(setting=simple_setting, knowledge_graph=populated_graph)
        second = GameState(setting=simple_setting, knowledge_graph=empty_graph)

        assert first.world_state is not second.world_state
        first.world_state.threads.append(
            WorldThread(description="x", category="political", introduced_scene=1),
        )
        assert second.world_state.threads == []


@allure.epic("Persistence")
@allure.feature("Domain↔row converters")
class TestWorldStateConverter:
    @allure.story("Round-trip")
    @allure.title("WorldState with threads and mood survives a serialise→dict→rehydrate round-trip")
    def test_round_trip_with_content(self):
        original = WorldState(
            threads=[
                WorldThread(
                    description="A plague spreads in the docks district",
                    category="natural",
                    introduced_scene=1,
                    involved_locations=[make_uuid("loc-1"), make_uuid("loc-2")],
                    involved_npcs=[make_uuid("npc-1")],
                    status="open",
                    last_advanced_scene=2,
                ),
                WorldThread(
                    description="Old debts come due for the miller",
                    category="personal",
                    introduced_scene=3,
                    status="resolved",
                ),
            ],
            world_mood="uneasy and watchful",
            last_chronicled_scene=4,
        )

        payload = conv_world_state.world_state_to_dict(original)
        assert payload["world_mood"] == "uneasy and watchful"
        assert payload["last_chronicled_scene"] == 4
        assert len(payload["threads"]) == 2

        restored = conv_world_state.dict_to_world_state(payload)
        assert restored.world_mood == "uneasy and watchful"
        assert restored.last_chronicled_scene == 4
        assert len(restored.threads) == 2
        assert restored.threads[0].description == "A plague spreads in the docks district"
        assert restored.threads[0].category == "natural"
        assert restored.threads[0].involved_locations == [make_uuid("loc-1"), make_uuid("loc-2")]
        assert restored.threads[0].involved_npcs == [make_uuid("npc-1")]
        assert restored.threads[0].last_advanced_scene == 2
        assert restored.threads[0].uuid == original.threads[0].uuid
        assert restored.threads[1].status == "resolved"
        assert restored.threads[1].category == "personal"

    @allure.story("Round-trip")
    @allure.title("Empty WorldState round-trips through the converter unchanged")
    def test_round_trip_empty(self):
        original = WorldState()
        payload = conv_world_state.world_state_to_dict(original)
        restored = conv_world_state.dict_to_world_state(payload)
        assert restored.threads == []
        assert restored.world_mood is None
        assert restored.last_chronicled_scene == 0

    @allure.story("Backwards compatibility")
    @allure.title("dict_to_world_state returns a fresh empty WorldState when the JSONB column is NULL")
    def test_null_payload_yields_empty_state(self):
        state = conv_world_state.dict_to_world_state(None)
        assert isinstance(state, WorldState)
        assert state.threads == []
        assert state.world_mood is None

    @allure.story("Backwards compatibility")
    @allure.title("dict_to_world_state returns a fresh empty WorldState when the JSONB column is an empty dict")
    def test_empty_payload_yields_empty_state(self):
        state = conv_world_state.dict_to_world_state({})
        assert isinstance(state, WorldState)
        assert state.threads == []
        assert state.world_mood is None

    @allure.story("Validation")
    @allure.title("dict_to_world_state raises ValueError on an unknown thread category")
    def test_invalid_category_rejected(self):
        bad = {
            "threads": [
                {
                    "description": "invalid",
                    "category": "dramatic",
                    "introduced_scene": 1,
                },
            ],
        }
        try:
            conv_world_state.dict_to_world_state(bad)
        except ValueError as exc:
            assert "dramatic" in str(exc)
        else:
            raise AssertionError("expected ValueError for unknown category")

    @allure.story("Validation")
    @allure.title("dict_to_world_state raises ValueError on an unknown thread status")
    def test_invalid_status_rejected(self):
        bad = {
            "threads": [
                {
                    "description": "invalid",
                    "category": "political",
                    "introduced_scene": 1,
                    "status": "pending",
                },
            ],
        }
        try:
            conv_world_state.dict_to_world_state(bad)
        except ValueError as exc:
            assert "pending" in str(exc)
        else:
            raise AssertionError("expected ValueError for unknown status")

    @allure.story("Backwards compatibility")
    @allure.title("dict_to_world_state accepts legacy payloads carrying a top-level uuid key")
    def test_legacy_uuid_key_ignored(self):
        legacy = {
            "uuid": "legacy-world-state-id",
            "threads": [],
            "world_mood": None,
            "last_chronicled_scene": 0,
        }
        state = conv_world_state.dict_to_world_state(legacy)
        assert isinstance(state, WorldState)
        assert not hasattr(state, "uuid")
