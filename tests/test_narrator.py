"""Tests for Narrator scene_type behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from cast.narrator import Narrator
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.scene import Scene, SceneNPC
from models.setting import Setting
from prompts.narrator_prompts import NARRATOR_SYSTEM


def _make_game_state() -> GameState:
    setting = Setting(
        name="Ancient Rome",
        time_period="1st century AD",
        region="Italy",
        summary="The Roman Empire.",
    )
    kg = KnowledgeGraph()
    gs = GameState(setting=setting, knowledge_graph=kg)
    gs.current_scene = Scene(
        location_id="forum",
        description="The bustling Roman Forum.",
        npcs_present=[SceneNPC(role="guard", uuid="npc-1")],
        points_of_interest=["fountain"],
        ambient_description="The air smells of roasted nuts.",
    )
    return gs


def _make_narrator() -> Narrator:
    llm_client = AsyncMock()
    llm_client.send_message = AsyncMock(
        return_value=AsyncMock(
            content="Narrated text.",
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )
    )
    return Narrator(llm_client=llm_client, language="English")


class TestNarratorSceneType:
    @pytest.mark.asyncio
    async def test_new_scene_passes_scene_type_new(self):
        narrator = _make_narrator()
        gs = _make_game_state()
        scene = gs.current_scene

        await narrator.act(
            input_data={"scene": scene},
            context={"player_action": "go to the forum", "game_state": gs},
        )

        # Check that the LLM was called with NEW_SCENE in the prompt
        call_args = narrator.llm_client.send_message.call_args
        messages = call_args.kwargs["messages"]
        user_msg = messages[-1].content
        assert "NEW_SCENE" in user_msg

    @pytest.mark.asyncio
    async def test_continuation_passes_scene_type_continuation(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data={"dialogue": [{"npc_name": "Marcus", "response": "Hello."}]},
            context={"player_action": "talk to Marcus", "game_state": gs},
        )

        call_args = narrator.llm_client.send_message.call_args
        messages = call_args.kwargs["messages"]
        user_msg = messages[-1].content
        assert "CONTINUATION" in user_msg

    @pytest.mark.asyncio
    async def test_new_scene_includes_ambient_description(self):
        narrator = _make_narrator()
        gs = _make_game_state()
        scene = gs.current_scene

        await narrator.act(
            input_data={"scene": scene},
            context={"player_action": "explore", "game_state": gs},
        )

        call_args = narrator.llm_client.send_message.call_args
        messages = call_args.kwargs["messages"]
        user_msg = messages[-1].content
        assert "Atmosphere:" in user_msg
        assert "roasted nuts" in user_msg

    @pytest.mark.asyncio
    async def test_continuation_excludes_scene_description(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data={},
            context={"player_action": "look around", "game_state": gs},
        )

        call_args = narrator.llm_client.send_message.call_args
        messages = call_args.kwargs["messages"]
        user_msg = messages[-1].content
        # No scene/atmosphere data should be in the prompt
        assert "Atmosphere:" not in user_msg
        assert "roasted nuts" not in user_msg
        assert "bustling Roman Forum" not in user_msg

    @pytest.mark.asyncio
    async def test_continuation_with_dialogue_only(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data={"dialogue": [{"npc_name": "Guard", "response": "Halt!"}]},
            context={"player_action": "approach guard", "game_state": gs},
        )

        call_args = narrator.llm_client.send_message.call_args
        messages = call_args.kwargs["messages"]
        user_msg = messages[-1].content
        assert "Guard says: Halt!" in user_msg
        assert "Atmosphere:" not in user_msg


class TestNarratorSceneHistory:
    @pytest.mark.asyncio
    async def test_continuation_includes_scene_history(self):
        """On CONTINUATION turns, scene history should appear in the prompt."""
        narrator = _make_narrator()
        gs = _make_game_state()
        scene_history = [
            {"player_action": "punch guard", "response_summary": "Guard blocks your fist.", "action_type": "INTERACT"},
        ]

        await narrator.act(
            input_data={"dialogue": [{"npc_name": "Guard", "response": "Stop!"}]},
            context={
                "player_action": "punch again",
                "game_state": gs,
                "scene_history": scene_history,
            },
        )

        call_args = narrator.llm_client.send_message.call_args
        messages = call_args.kwargs["messages"]
        user_msg = messages[-1].content
        assert "What happened earlier" in user_msg
        assert "punch guard" in user_msg
        assert "Guard blocks" in user_msg

    @pytest.mark.asyncio
    async def test_new_scene_ignores_scene_history(self):
        """On NEW_SCENE turns, scene history should NOT appear."""
        narrator = _make_narrator()
        gs = _make_game_state()
        scene_history = [
            {"player_action": "old action", "response_summary": "old response", "action_type": "TALK"},
        ]

        await narrator.act(
            input_data={"scene": gs.current_scene},
            context={
                "player_action": "go to market",
                "game_state": gs,
                "scene_history": scene_history,
            },
        )

        call_args = narrator.llm_client.send_message.call_args
        messages = call_args.kwargs["messages"]
        user_msg = messages[-1].content
        assert "What happened earlier" not in user_msg

    @pytest.mark.asyncio
    async def test_continuation_without_scene_history(self):
        """CONTINUATION with no scene_history should still work."""
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data={"dialogue": [{"npc_name": "Guard", "response": "Hello."}]},
            context={
                "player_action": "greet guard",
                "game_state": gs,
            },
        )

        call_args = narrator.llm_client.send_message.call_args
        messages = call_args.kwargs["messages"]
        user_msg = messages[-1].content
        assert "What happened earlier" not in user_msg
        assert "Guard says: Hello." in user_msg


class TestNarratorSystemPrompt:
    def test_system_prompt_mentions_new_scene_and_continuation(self):
        """Verify the system prompt contains guidance for both modes."""
        rendered = NARRATOR_SYSTEM.render(
            setting_name="Test",
            time_period="Now",
            time_of_day="morning",
            language="English",
        )
        assert "NEW SCENE" in rendered
        assert "CONTINUATION" in rendered
