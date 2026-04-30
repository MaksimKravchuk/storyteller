"""Tests for Narrator scene_type behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast.narrator import Narrator, _build_narrator_context_kwargs
from cast.schemas.turn_outputs import DialogueEntry, TurnOutputs
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.scene import PointOfInterest, Scene, SceneNPC
from models.setting import Setting
from prompts.narrator_prompts import NARRATOR_SYSTEM

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PLAYER_ACTION = "player_action"
_GAME_STATE = "game_state"
_MESSAGES = "messages"


def _last_user_message(narrator: Narrator) -> str:
    """Extract the last user message sent to the LLM."""
    call_kwargs = narrator.llm_client.send_message.call_args.kwargs  # type: ignore[attr-defined]
    return call_kwargs[_MESSAGES][-1].body


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
        points_of_interest=[PointOfInterest(names=["fountain"])],
        ambient_description="The air smells of roasted nuts.",
    )
    return gs


def _make_narrator() -> Narrator:
    llm_client = AsyncMock()
    llm_client.send_message = AsyncMock(
        return_value=AsyncMock(
            body="Narrated text.",
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )
    )
    return Narrator(llm_client=llm_client, language="English")


@allure.epic("Narrative Delivery")
@allure.feature("Narrator")
class TestNarratorSceneType:
    @allure.story("Scene type selection")
    @allure.title("Narrator receives NEW_SCENE marker when the turn introduces a fresh location")
    @pytest.mark.asyncio
    async def test_new_scene_passes_scene_type_new(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(scene=gs.current_scene),
            context={_PLAYER_ACTION: "go to the forum", _GAME_STATE: gs},
        )

        # Check that the LLM was called with NEW_SCENE in the prompt
        user_msg = _last_user_message(narrator)
        assert "NEW_SCENE" in user_msg

    @allure.story("Scene type selection")
    @allure.title("Narrator receives CONTINUATION marker when the turn extends the current scene")
    @pytest.mark.asyncio
    async def test_continuation_passes_scene_type(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(dialogue=[DialogueEntry(npc_name="Marcus", response="Hello.")]),
            context={_PLAYER_ACTION: "talk to Marcus", _GAME_STATE: gs},
        )

        user_msg = _last_user_message(narrator)
        assert "CONTINUATION" in user_msg

    @allure.story("Scene type selection")
    @allure.title("New-scene prompt includes the scene's ambient atmosphere description")
    @pytest.mark.asyncio
    async def test_new_scene_includes_ambient_description(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(scene=gs.current_scene),
            context={_PLAYER_ACTION: "explore", _GAME_STATE: gs},
        )

        user_msg = _last_user_message(narrator)
        assert "Atmosphere:" in user_msg
        assert "roasted nuts" in user_msg

    @allure.story("Scene type selection")
    @allure.title("Continuation prompt omits scene description and atmosphere to avoid re-describing the setting")
    @pytest.mark.asyncio
    async def test_continuation_excludes_scene_description(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(),
            context={_PLAYER_ACTION: "look around", _GAME_STATE: gs},
        )

        call_args = narrator.llm_client.send_message.call_args
        messages = call_args.kwargs[_MESSAGES]
        user_msg = messages[-1].body
        # No scene/atmosphere data should be in the prompt
        assert "Atmosphere:" not in user_msg
        assert "roasted nuts" not in user_msg
        assert "bustling Roman Forum" not in user_msg

    @allure.story("Dialogue rendering")
    @allure.title("Continuation prompt surfaces NPC dialogue lines in 'Name says: text' format")
    @pytest.mark.asyncio
    async def test_continuation_with_dialogue_only(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(dialogue=[DialogueEntry(npc_name="Guard", response="Halt!")]),
            context={_PLAYER_ACTION: "approach guard", _GAME_STATE: gs},
        )

        call_args = narrator.llm_client.send_message.call_args
        messages = call_args.kwargs[_MESSAGES]
        user_msg = messages[-1].body
        assert "Guard says: Halt!" in user_msg
        assert "Atmosphere:" not in user_msg


@allure.epic("Narrative Delivery")
@allure.feature("Narrator")
class TestNarratorSceneHistory:
    @allure.story("Scene history")
    @allure.title("Continuation prompt injects prior in-scene actions under a 'What happened earlier' heading")
    @pytest.mark.asyncio
    async def test_continuation_includes_scene_history(self):
        """On CONTINUATION turns, scene history should appear in the prompt."""
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(dialogue=[DialogueEntry(npc_name="Guard", response="Stop!")]),
            context={
                _PLAYER_ACTION: "punch again",
                _GAME_STATE: gs,
                "scene_history": [
                    {
                        _PLAYER_ACTION: "punch guard",
                        "response_summary": "Guard blocks your fist.",
                        "action_type": "INTERACT",
                    },
                ],
            },
        )

        user_msg = _last_user_message(narrator)
        assert "What happened earlier" in user_msg
        assert "punch guard" in user_msg
        assert "Guard blocks" in user_msg

    @allure.story("Scene history")
    @allure.title("New-scene prompt ignores scene history because the prior scene is no longer relevant")
    @pytest.mark.asyncio
    async def test_new_scene_ignores_scene_history(self):
        """On NEW_SCENE turns, scene history should NOT appear."""
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(scene=gs.current_scene),
            context={
                _PLAYER_ACTION: "go to market",
                _GAME_STATE: gs,
                "scene_history": [
                    {_PLAYER_ACTION: "old action", "response_summary": "old response", "action_type": "TALK"},
                ],
            },
        )

        user_msg = _last_user_message(narrator)
        assert "What happened earlier" not in user_msg

    @allure.story("Scene history")
    @allure.title("Continuation still renders dialogue even when there is no scene history to attach")
    @pytest.mark.asyncio
    async def test_continuation_without_scene_history(self):
        """CONTINUATION with no scene_history should still work."""
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(dialogue=[DialogueEntry(npc_name="Guard", response="Hello.")]),
            context={
                _PLAYER_ACTION: "greet guard",
                _GAME_STATE: gs,
            },
        )

        call_args = narrator.llm_client.send_message.call_args
        messages = call_args.kwargs[_MESSAGES]
        user_msg = messages[-1].body
        assert "What happened earlier" not in user_msg
        assert "Guard says: Hello." in user_msg


@allure.epic("Narrative Delivery")
@allure.feature("Narrator")
class TestNarratorSystemPrompt:
    @allure.story("System prompt")
    @allure.title("Narrator system prompt documents both NEW SCENE and CONTINUATION narration modes")
    def test_system_prompt_has_scene_modes(self):
        """Verify the system prompt contains guidance for both modes."""
        rendered = NARRATOR_SYSTEM.render(
            setting_name="Test",
            time_period="Now",
            time_of_day="morning",
            language="English",
            player_appearance="unremarkable",
            player_inventory="nothing of note",
        )
        assert "NEW SCENE" in rendered
        assert "CONTINUATION" in rendered

    @allure.story("System prompt")
    @allure.title("Narrator system prompt renders player appearance and inventory when both are present")
    def test_system_prompt_renders_player_character_section(self):
        rendered = NARRATOR_SYSTEM.render(
            setting_name="Test",
            time_period="Now",
            time_of_day="morning",
            language="English",
            player_appearance="grey hoodie",
            player_inventory="phone, keys",
        )
        assert "grey hoodie" in rendered
        assert "phone, keys" in rendered


@allure.epic("Narrative Delivery")
@allure.feature("Narrator")
class TestNarratorContextKwargs:
    @allure.story("Player character context")
    @allure.title("_build_narrator_context_kwargs always supplies player_appearance and player_inventory")
    def test_context_kwargs_include_player_vars(self):
        gs = _make_game_state()
        gs.player.appearance = "grey hoodie"
        gs.player.inventory = ["phone", "keys"]

        kwargs = _build_narrator_context_kwargs(gs, language="English", is_new_scene=False)

        assert kwargs["player_appearance"] == "grey hoodie"
        assert kwargs["player_inventory"] == "phone, keys"

    @allure.story("Player character context")
    @allure.title("_build_narrator_context_kwargs falls back to neutral defaults when the player is anonymous")
    def test_context_kwargs_player_vars_default(self):
        gs = _make_game_state()

        kwargs = _build_narrator_context_kwargs(gs, language="English", is_new_scene=False)

        assert kwargs["player_appearance"] == "unremarkable"
        assert kwargs["player_inventory"] == "nothing of note"
