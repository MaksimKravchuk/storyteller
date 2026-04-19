"""Tests that the Narrator prompt surfaces turn intent (KER-19).

When :attr:`TurnOutputs.intent` is set, the Narrator prompt template
renders an extra guidance section that tells the LLM to honor the
player's stated intent — or explicitly acknowledge a contradiction
between the intent and the raw material it has to narrate.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast.narrator import Narrator
from cast.schemas.turn_outputs import DialogueEntry, TurnOutputs
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.scene import PointOfInterest, Scene, SceneNPC
from models.setting import Setting

_PLAYER_ACTION = "player_action"
_GAME_STATE = "game_state"
_MESSAGES = "messages"
_INTENT = "return to the Forum and speak to the guard"


def _last_user_message(narrator: Narrator) -> str:
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
    )
    return gs


def _make_narrator() -> Narrator:
    llm_client = AsyncMock()
    llm_client.send_message = AsyncMock(
        return_value=AsyncMock(
            body="Narrated text.",
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        ),
    )
    return Narrator(llm_client=llm_client, language="English")


@allure.epic("Narrative Delivery")
@allure.feature("Narrator")
class TestNarratorHonorsIntent:
    @allure.story("Turn intent")
    @allure.title("Narrator prompt surfaces the player's stated intent alongside 'Honor this intent' guidance")
    @pytest.mark.asyncio
    async def test_intent_renders_in_prompt(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(
                dialogue=[DialogueEntry(npc_name="Guard", response="Halt!")],
                intent=_INTENT,
            ),
            context={_PLAYER_ACTION: "speak to the guard", _GAME_STATE: gs},
        )

        user_msg = _last_user_message(narrator)
        assert _INTENT in user_msg
        assert "Honor this intent" in user_msg

    @allure.story("Turn intent")
    @allure.title("Narrator prompt omits the turn-intent section when TurnOutputs.intent is None")
    @pytest.mark.asyncio
    async def test_intent_section_skipped_when_absent(self):
        narrator = _make_narrator()
        gs = _make_game_state()

        await narrator.act(
            input_data=TurnOutputs(
                dialogue=[DialogueEntry(npc_name="Guard", response="Halt!")],
            ),
            context={_PLAYER_ACTION: "greet guard", _GAME_STATE: gs},
        )

        user_msg = _last_user_message(narrator)
        assert "Honor this intent" not in user_msg
        assert "stated intent for this turn" not in user_msg
