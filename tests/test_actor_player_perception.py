"""Regression tests: NPCs perceive the player's appearance, not just their action.

Before this fix, the Actor prompt received only the player's action text —
so a 190 cm Slav strolling through 1st-century Rome and a local farmhand
elicited the same flat reaction. Two layers are guarded:

* the prompt template (``player_character`` section renders appearance + era);
* the Actor consumer wiring (``Actor.act`` extracts ``game_state.player`` and
  ``game_state.setting`` into the rendering context).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast.actor import Actor
from cast.schemas.actor_reply import ActorEnvelope
from knowledge.graph import KnowledgeGraph
from knowledge.query import KnowledgeQueryEngine
from models.npc_card import NPCCard
from prompts.actor_prompts import ACTOR_SYSTEM_DIALOGUE
from prompts.actor_prompts_ru import ACTOR_SYSTEM_DIALOGUE_RU
from tests.actor_helpers import render_actor_system


def _make_actor(monkeypatch: pytest.MonkeyPatch) -> Actor:
    """Build an Actor whose envelope path returns a fixed empty narration.

    Patching via ``monkeypatch.setattr`` keeps mypy quiet (no method-assign
    error) and ensures the patched method is restored after the test.
    """
    actor = Actor(
        llm_client=AsyncMock(),
        npc=NPCCard(name="Cassius", occupation="senator"),
        knowledge_query=KnowledgeQueryEngine(KnowledgeGraph()),
    )
    monkeypatch.setattr(actor, "_send_json", AsyncMock(return_value=ActorEnvelope(narration="...")))
    return actor


@allure.epic("NPC Interaction")
@allure.feature("Player perception")
class TestActorPromptPlayerPerception:
    """The Actor system prompt must surface the player's visible appearance
    and the setting era so NPC reactions can register out-of-place visitors.
    """

    @allure.story("Player appearance in prompt")
    @allure.title("Actor prompt declares player_appearance, setting_name, time_period as required vars")
    def test_player_perception_vars_required(self):
        required = ACTOR_SYSTEM_DIALOGUE.required_vars
        assert "player_appearance" in required
        assert "setting_name" in required
        assert "time_period" in required

    @allure.story("Player appearance in prompt")
    @allure.title("Actor prompt interpolates the player's appearance into the rendered system prompt")
    def test_prompt_contains_player_appearance(self):
        rendered = render_actor_system(player_appearance="190 cm tall, fair-skinned, in heavy furs")
        assert "190 cm tall, fair-skinned, in heavy furs" in rendered

    @allure.story("Setting era in prompt")
    @allure.title("Actor prompt interpolates setting name and time period so era is comparable")
    def test_prompt_contains_setting_era(self):
        rendered = render_actor_system(setting_name="Ancient Rome", time_period="1st century BCE")
        assert "Ancient Rome" in rendered
        assert "1st century BCE" in rendered

    @allure.story("Russian catalog parity")
    @allure.title("Russian Actor prompt also surfaces player appearance and setting era")
    def test_russian_prompt_contains_player_perception(self):
        rendered = ACTOR_SYSTEM_DIALOGUE_RU.render(
            npc_name="Маркус",
            npc_occupation="легионер",
            location_name="форум",
            npc_biography="Ветеран легиона.",
            personality_traits="суровый",
            speech_style="отрывистый",
            npc_appearance="загорелый, в доспехе",
            npc_inventory="гладий",
            accessible_knowledge="Форум закрывается на закате.",
            current_mood="neutral",
            physical_status="healthy",
            language="Russian",
            player_appearance="ростом 190 см, светлокожий, в звериных шкурах",
            setting_name="Древний Рим",
            time_period="I век до н.э.",
        )
        assert "190 см" in rendered
        assert "Древний Рим" in rendered
        assert "I век до н.э." in rendered


@allure.epic("NPC Interaction")
@allure.feature("Player perception")
class TestActorConsumerWiresPlayerPerception:
    """Consumer-side regression: ``Actor.act`` must read the player's
    appearance and the setting's era off ``game_state`` and feed them
    into the system prompt context — the gap that this fix closes.
    """

    @pytest.mark.asyncio
    @allure.story("Consumer wiring")
    @allure.title("Actor.act extracts player appearance from game_state into the rendered system prompt")
    async def test_act_renders_player_appearance_into_system_prompt(self, game_state, monkeypatch):
        actor = _make_actor(monkeypatch)
        game_state.player.appearance = "190 cm tall, in dark furs, speaks with a heavy northern accent"

        await actor.act(
            "I greet you.",
            context={"game_state": game_state, "location_name": "Forum"},
        )

        rendered = actor.system_prompt_template.render(**actor._system_prompt_vars)
        assert "190 cm tall, in dark furs" in rendered
        assert game_state.setting.name in rendered
        assert game_state.setting.time_period in rendered

    @pytest.mark.asyncio
    @allure.story("Consumer wiring")
    @allure.title("Actor.act tolerates missing game_state — the player section is simply skipped")
    async def test_act_without_game_state_skips_player_section(self, monkeypatch):
        actor = _make_actor(monkeypatch)
        await actor.act("I greet you.", context={"location_name": "Forum"})
        assert "player_appearance" not in actor._system_prompt_vars
