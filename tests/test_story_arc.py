"""Tests for the StoryArc data model and its converter bridge.

These cover the pure data plumbing for the upcoming Playwright agent:
default factories, value defaults on Beat / PlotThread, the
JSONB round-trip via :mod:`db.converters.story_arc`, and the
``GameState.story_arc`` default-factory independence guarantee.
"""

from __future__ import annotations

import allure

from db.converters import story_arc as conv_story_arc
from models.game_state import GameState
from models.story_arc import Beat, PlotThread, StoryArc


@allure.epic("Memory & Persistence")
@allure.feature("StoryArc model")
class TestStoryArcDefaults:
    @allure.story("Defaults")
    @allure.title("A new StoryArc starts at act 1 with no current beat and empty beats/threads lists")
    def test_default_values(self):
        arc = StoryArc()
        assert arc.act == 1
        assert arc.current_beat_id is None
        assert arc.beats == []
        assert arc.threads == []

    @allure.story("Defaults")
    @allure.title("A new StoryArc receives a UUID from BaseModel automatically")
    def test_uuid_assigned(self):
        arc = StoryArc()
        assert isinstance(arc.uuid, str)
        assert arc.uuid


@allure.epic("Memory & Persistence")
@allure.feature("StoryArc model")
class TestBeatDefaults:
    @allure.story("Defaults")
    @allure.title("A new Beat with description and kind defaults resolved to False")
    def test_resolved_default_false(self):
        beat = Beat(description="The hero arrives in town.", kind="setup")
        assert beat.description == "The hero arrives in town."
        assert beat.kind == "setup"
        assert beat.resolved is False

    @allure.story("Defaults")
    @allure.title("A Beat receives its own UUID from BaseModel separate from any other beat")
    def test_each_beat_has_independent_uuid(self):
        beat_a = Beat(description="A", kind="setup")
        beat_b = Beat(description="B", kind="rising")
        assert beat_a.uuid != beat_b.uuid


@allure.epic("Memory & Persistence")
@allure.feature("StoryArc model")
class TestPlotThreadDefaults:
    @allure.story("Defaults")
    @allure.title("A new PlotThread with description and introduced_scene defaults status to 'open'")
    def test_status_default_open(self):
        thread = PlotThread(description="The missing heir", introduced_scene=1)
        assert thread.description == "The missing heir"
        assert thread.introduced_scene == 1
        assert thread.status == "open"
        assert thread.involved_npcs == []

    @allure.story("Defaults")
    @allure.title("PlotThread.involved_npcs is independent across instances thanks to default_factory")
    def test_involved_npcs_independent_per_instance(self):
        thread_a = PlotThread(description="A", introduced_scene=1)
        thread_b = PlotThread(description="B", introduced_scene=2)
        thread_a.involved_npcs.append("npc-1")
        assert thread_b.involved_npcs == []


@allure.epic("Memory & Persistence")
@allure.feature("StoryArc model")
class TestGameStateStoryArcField:
    @allure.story("GameState plumbing")
    @allure.title("GameState exposes a story_arc field that defaults to an empty StoryArc")
    def test_default_story_arc(self, game_state):
        assert isinstance(game_state.story_arc, StoryArc)
        assert game_state.story_arc.act == 1
        assert game_state.story_arc.beats == []
        assert game_state.story_arc.threads == []

    @allure.story("GameState plumbing")
    @allure.title("Two GameState instances each receive their own independent StoryArc object")
    def test_default_factory_isolates_instances(self, simple_setting, populated_graph, empty_graph):
        first = GameState(setting=simple_setting, knowledge_graph=populated_graph)
        second = GameState(setting=simple_setting, knowledge_graph=empty_graph)

        assert first.story_arc is not second.story_arc
        first.story_arc.beats.append(Beat(description="setup", kind="setup"))
        assert second.story_arc.beats == []


@allure.epic("Persistence")
@allure.feature("Domain↔row converters")
class TestStoryArcConverter:
    @allure.story("Round-trip")
    @allure.title("StoryArc with beats and threads survives a serialise→dict→rehydrate round-trip")
    def test_round_trip_with_content(self):
        original = StoryArc(
            act=2,
            current_beat_id="beat-uuid-1",
            beats=[
                Beat(description="Hero meets mentor", kind="setup", resolved=True),
                Beat(description="Inciting incident", kind="rising"),
            ],
            threads=[
                PlotThread(
                    description="The missing heir",
                    introduced_scene=1,
                    involved_npcs=["npc-1", "npc-2"],
                    status="open",
                ),
                PlotThread(
                    description="Old debts",
                    introduced_scene=3,
                    status="resolved",
                ),
            ],
        )

        payload = conv_story_arc.story_arc_to_dict(original)
        assert payload["act"] == 2
        assert payload["current_beat_id"] == "beat-uuid-1"
        assert len(payload["beats"]) == 2
        assert len(payload["threads"]) == 2

        restored = conv_story_arc.dict_to_story_arc(payload)
        assert restored.uuid == original.uuid
        assert restored.act == 2
        assert restored.current_beat_id == "beat-uuid-1"
        assert len(restored.beats) == 2
        assert restored.beats[0].description == "Hero meets mentor"
        assert restored.beats[0].kind == "setup"
        assert restored.beats[0].resolved is True
        assert restored.beats[0].uuid == original.beats[0].uuid
        assert restored.beats[1].kind == "rising"
        assert restored.beats[1].resolved is False
        assert len(restored.threads) == 2
        assert restored.threads[0].description == "The missing heir"
        assert restored.threads[0].involved_npcs == ["npc-1", "npc-2"]
        assert restored.threads[0].status == "open"
        assert restored.threads[1].status == "resolved"

    @allure.story("Round-trip")
    @allure.title("Empty StoryArc round-trips through the converter unchanged")
    def test_round_trip_empty(self):
        original = StoryArc()
        payload = conv_story_arc.story_arc_to_dict(original)
        restored = conv_story_arc.dict_to_story_arc(payload)
        assert restored.uuid == original.uuid
        assert restored.act == 1
        assert restored.current_beat_id is None
        assert restored.beats == []
        assert restored.threads == []

    @allure.story("Backwards compatibility")
    @allure.title("dict_to_story_arc returns a fresh empty StoryArc when the JSONB column is NULL")
    def test_null_payload_yields_empty_arc(self):
        arc = conv_story_arc.dict_to_story_arc(None)
        assert isinstance(arc, StoryArc)
        assert arc.act == 1
        assert arc.beats == []
        assert arc.threads == []

    @allure.story("Backwards compatibility")
    @allure.title("dict_to_story_arc returns a fresh empty StoryArc when the JSONB column is an empty dict")
    def test_empty_payload_yields_empty_arc(self):
        arc = conv_story_arc.dict_to_story_arc({})
        assert isinstance(arc, StoryArc)
        assert arc.act == 1
        assert arc.beats == []
        assert arc.threads == []
