"""Tests for the World Chronicler performer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from cast.schemas.chronicler_response import (
    ChroniclerResponse,
    ScheduledEventDraft,
    WorldThreadDraft,
    WorldThreadUpdate,
)
from cast.schemas.turn_outputs import TurnOutputs
from cast.world_chronicler import WorldChronicler, _format_threads, _summarize_turn
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.scene import Scene, SceneNPC
from models.setting import Setting
from models.world_state import WorldThread


def _make_game_state() -> GameState:
    setting = Setting(
        name="Florence",
        time_period="1480s",
        region="Tuscany",
        summary="A merchant republic flush with Medici gold.",
    )
    gs = GameState(setting=setting, knowledge_graph=KnowledgeGraph())
    gs.current_scene = Scene(
        location_id="piazza",
        description="The Piazza della Signoria at dawn.",
        npcs_present=[SceneNPC(role="guard")],
        ambient_description="Bells echo off stone.",
    )
    gs.scene_number = 3
    return gs


def _make_chronicler(response_payload: dict | Exception) -> WorldChronicler:
    llm_client = AsyncMock()
    chronicler = WorldChronicler(llm_client=llm_client)
    if isinstance(response_payload, Exception):
        chronicler._send_json = AsyncMock(side_effect=response_payload)  # type: ignore[method-assign]
    else:
        chronicler._send_json = AsyncMock(  # type: ignore[method-assign]
            return_value=ChroniclerResponse.model_validate(response_payload),
        )
    return chronicler


@allure.epic("Narrative Delivery")
@allure.feature("World Chronicler")
class TestChroniclerHappyPath:
    @allure.story("Happy path")
    @allure.title("Chronicler returns a validated ChroniclerResponse with new threads and a mood")
    @pytest.mark.asyncio
    async def test_happy_path_parses_response(self):
        payload = {
            "new_threads": [
                {
                    "description": "A plague whisper spreads through the docks",
                    "category": "natural",
                    "involved_locations": ["loc-1"],
                    "involved_npcs": [],
                },
            ],
            "thread_updates": [],
            "scheduled_events": [],
            "world_mood": "uneasy, watchful",
        }
        chronicler = _make_chronicler(payload)
        gs = _make_game_state()

        response = await chronicler.act(
            input_data=TurnOutputs(scene=gs.current_scene),
            context={"game_state": gs, "player_action": "explore"},
        )

        assert isinstance(response, ChroniclerResponse)
        assert len(response.new_threads) == 1
        assert response.new_threads[0].description == "A plague whisper spreads through the docks"
        assert response.new_threads[0].category == "natural"
        assert response.world_mood == "uneasy, watchful"

    @allure.story("Happy path")
    @allure.title("Chronicler builds a prompt that includes current open threads and scene number")
    @pytest.mark.asyncio
    async def test_prompt_mentions_open_threads_and_scene_number(self):
        chronicler = _make_chronicler({})
        gs = _make_game_state()
        gs.world_state.threads.append(
            WorldThread(
                description="The miller owes the guild money",
                category="economic",
                introduced_scene=1,
            ),
        )

        await chronicler.act(
            input_data=TurnOutputs(scene=gs.current_scene),
            context={"game_state": gs, "player_action": "walk"},
        )

        prompt = chronicler._send_json.call_args.args[0]  # type: ignore[attr-defined]
        assert "Scene number: 3" in prompt
        assert "The miller owes the guild money" in prompt


@allure.epic("Narrative Delivery")
@allure.feature("World Chronicler")
class TestChroniclerEmptyResponse:
    @allure.story("Empty output")
    @allure.title("Chronicler accepts a default empty ChroniclerResponse with no changes")
    @pytest.mark.asyncio
    async def test_empty_payload_returns_empty_response(self):
        chronicler = _make_chronicler({})
        gs = _make_game_state()

        response = await chronicler.act(
            input_data=TurnOutputs(scene=gs.current_scene),
            context={"game_state": gs, "player_action": "idle"},
        )

        assert response.new_threads == []
        assert response.thread_updates == []
        assert response.scheduled_events == []
        assert response.world_mood is None


@allure.epic("Narrative Delivery")
@allure.feature("World Chronicler")
class TestChroniclerMalformedJson:
    @allure.story("Retries exhausted")
    @allure.title("Chronicler surfaces ValueError from _send_json when retries are exhausted")
    @pytest.mark.asyncio
    async def test_retries_exhausted_raises(self):
        chronicler = _make_chronicler(ValueError("Agent failed to produce valid JSON"))
        gs = _make_game_state()

        with pytest.raises(ValueError, match="valid JSON"):
            await chronicler.act(
                input_data=TurnOutputs(scene=gs.current_scene),
                context={"game_state": gs, "player_action": "idle"},
            )


@allure.epic("Narrative Delivery")
@allure.feature("World Chronicler")
class TestChroniclerHelpers:
    @allure.story("Prompt helpers")
    @allure.title("_format_threads renders a placeholder when there are no open threads")
    def test_format_threads_empty(self):
        rendered = _format_threads([])
        assert rendered == "(no open threads)"

    @allure.story("Prompt helpers")
    @allure.title("_format_threads skips resolved/abandoned threads and numbers the rest")
    def test_format_threads_filters_status(self):
        threads = [
            WorldThread(description="A", category="political", introduced_scene=1, status="open"),
            WorldThread(description="B", category="social", introduced_scene=1, status="resolved"),
            WorldThread(description="C", category="economic", introduced_scene=2, status="open"),
        ]
        rendered = _format_threads(threads)
        assert "1." in rendered
        assert "2." in rendered
        assert "A" in rendered
        assert "C" in rendered
        assert "B" not in rendered

    @allure.story("Prompt helpers")
    @allure.title("_summarize_turn returns a placeholder when the turn was a no-op")
    def test_summarize_turn_empty(self):
        assert _summarize_turn(TurnOutputs()) == "(nothing notable happened)"

    @allure.story("Prompt helpers")
    @allure.title("_summarize_turn includes scene, dialogue, departures, and completed events")
    def test_summarize_turn_includes_all_branches(self):
        scene = Scene(location_id="tavern", description="A smoky tavern")
        summary = _summarize_turn(
            TurnOutputs(
                scene=scene,
                new_npcs=["Carla (courier)"],
                item_examination=["A brass key"],
                npc_departures=["Marco leaves"],
                completed_events=["The storm passes"],
                wait=True,
                wait_reason="voluntary",
            ),
        )
        assert "Scene built" in summary
        assert "Carla" in summary
        assert "A brass key" in summary
        assert "Marco leaves" in summary
        assert "The storm passes" in summary
        assert "Player waited" in summary


@allure.epic("Narrative Delivery")
@allure.feature("World Chronicler")
class TestChroniclerResponseSchemaDefaults:
    @allure.story("Schema defaults")
    @allure.title("ChroniclerResponse fields all default to empty/None for a conservative agent")
    def test_response_defaults(self):
        response = ChroniclerResponse()
        assert response.new_threads == []
        assert response.thread_updates == []
        assert response.scheduled_events == []
        assert response.world_mood is None

    @allure.story("Schema defaults")
    @allure.title("ScheduledEventDraft defaults scope to 'remote' because most events are offscreen")
    def test_scheduled_event_draft_defaults(self):
        draft = ScheduledEventDraft(name="A courier arrives", hours_from_now=3.0)
        assert draft.scope == "remote"
        assert draft.location_id is None
        assert draft.on_complete_description == ""

    @allure.story("Schema defaults")
    @allure.title("WorldThreadUpdate accepts a None status to mean 'just bump last_advanced_scene'")
    def test_thread_update_status_optional(self):
        update = WorldThreadUpdate(thread_uuid="abc")
        assert update.status is None

    @allure.story("Schema defaults")
    @allure.title("WorldThreadDraft accepts empty involved_locations and involved_npcs lists")
    def test_thread_draft_default_lists(self):
        draft = WorldThreadDraft(description="something", category="cultural")
        assert draft.involved_locations == []
        assert draft.involved_npcs == []


@allure.epic("Narrative Delivery")
@allure.feature("World Chronicler")
class TestChroniclerFencedResponse:
    @allure.story("Markdown fence recovery")
    @allure.title(
        "WorldChronicler parses a ChroniclerResponse wrapped in markdown fences "
        "when the Anthropic client falls back to the prompt path",
    )
    @pytest.mark.asyncio
    async def test_fenced_json_parses_correctly(self):
        fenced = (
            '```json\n{"new_threads": [], "thread_updates": [], "scheduled_events": [], "world_mood": "ominous"}\n```'
        )
        chronicler = WorldChronicler(llm_client=MagicMock())
        gs = _make_game_state()

        with patch("cast.base_performer_class._send_json_strict", side_effect=NotImplementedError):
            with patch.object(chronicler, "_send", new=AsyncMock(return_value=fenced)):
                response = await chronicler.act(
                    input_data=TurnOutputs(scene=gs.current_scene),
                    context={"game_state": gs, "player_action": "explore"},
                )

        assert isinstance(response, ChroniclerResponse)
        assert response.world_mood == "ominous"
