"""Actor prompt consumer-seam tests for relevant memory selection."""

from __future__ import annotations

import allure
import pytest

from cast.actor import Actor
from knowledge.graph import KnowledgeGraph
from knowledge.node import EdgeType, KnowledgeNode, KnowledgeScope, KnowledgeSource
from knowledge.query import KnowledgeQueryEngine
from models.game_state import GameState, PlayerState
from models.goal import Goal, GoalKind, GoalStatus
from models.npc_card import NPCCard
from models.setting import Setting
from tests._uuid_helpers import make_uuid
from tests.prompts import _consumer_seam_kwargs as kwargs_mod

_ACTOR_ID = make_uuid("prompt-actor-memory-actor")
_PLAYER_ID = make_uuid("prompt-actor-memory-player")
_TARGET_ID = make_uuid("prompt-actor-memory-target")
_OTHER_ID = make_uuid("prompt-actor-memory-other")
_RELEVANT_TEXT = "The player spared Aulus at the gate."
_TARGET_TEXT = "Marcus bribed Aulus yesterday."
_CONCEPT_TEXT = "The player used light without flame."
_IRRELEVANT_TEXT = "Aulus counted coins at the market."
_ACTION_REPLY_JSON = '{"action": "watch Marcus", "type": "IDLE", "target": "Marcus"}'


def _attach_memory(
    graph: KnowledgeGraph,
    text: str,
    *,
    timestamp: float,
    salience: float,
    fields: dict | None = None,
) -> None:
    memory_fields = fields or {}
    memory = KnowledgeNode(
        text=text,
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.PERSONAL_EXPERIENCE,
        timestamp=timestamp,
        salience=salience,
        **memory_fields,
    )
    graph.add_node(memory)
    graph.add_edge(_ACTOR_ID, memory.uuid, EdgeType.WITNESSED)


def _build_actor_state() -> tuple[GameState, NPCCard]:
    graph = KnowledgeGraph()
    graph.register_actor_node(_ACTOR_ID, label="Aulus")
    _attach_memory(
        graph,
        _RELEVANT_TEXT,
        timestamp=1.0,
        salience=0.1,
        fields={"subject_id": _PLAYER_ID},
    )
    for idx in range(5):
        _attach_memory(
            graph,
            "{0} {1}".format(_IRRELEVANT_TEXT, idx),
            timestamp=10.0 + idx,
            salience=1.0,
            fields={"subject_id": _OTHER_ID},
        )
    actor = NPCCard(
        uuid=_ACTOR_ID,
        name="Aulus",
        occupation="guard",
        biography="A veteran guard.",
        personality_traits=["stern"],
        speech_style="curt",
    )
    state = GameState(
        setting=Setting(name="Rome", time_period="AD 64", region="Italia", summary=""),
        knowledge_graph=graph,
        player=PlayerState(uuid=_PLAYER_ID, name="Player"),
        npcs={_ACTOR_ID: actor},
    )
    return state, actor


def _build_actor_state_with_goal() -> tuple[GameState, NPCCard]:
    state, actor = _build_actor_state()
    actor.tactical_goal = Goal(
        kind=GoalKind.PURSUE,
        description="Watch Marcus.",
        target_uuid=_TARGET_ID,
        status=GoalStatus.ACTIVE,
    )
    _attach_memory(
        state.knowledge_graph,
        _TARGET_TEXT,
        timestamp=2.0,
        salience=0.2,
        fields={"subject_id": _TARGET_ID},
    )
    return state, actor


def _build_actor_state_without_fallback() -> tuple[GameState, NPCCard]:
    graph = KnowledgeGraph()
    graph.register_actor_node(_ACTOR_ID, label="Aulus")
    _attach_memory(
        graph,
        _RELEVANT_TEXT,
        timestamp=1.0,
        salience=0.1,
        fields={"subject_id": _PLAYER_ID},
    )
    actor = NPCCard(
        uuid=_ACTOR_ID,
        name="Aulus",
        occupation="guard",
        biography="A veteran guard.",
        personality_traits=["stern"],
        speech_style="curt",
    )
    state = GameState(
        setting=Setting(name="Rome", time_period="AD 64", region="Italia", summary=""),
        knowledge_graph=graph,
        player=PlayerState(uuid=_PLAYER_ID, name="Player"),
        npcs={_ACTOR_ID: actor},
    )
    return state, actor


def _build_actor_state_with_concept_memory() -> tuple[GameState, NPCCard]:
    state, actor = _build_actor_state()
    _attach_memory(
        state.knowledge_graph,
        _CONCEPT_TEXT,
        timestamp=2.0,
        salience=0.2,
        fields={
            "subject_id": _OTHER_ID,
            "tags": ["light_without_flame"],
        },
    )
    return state, actor


@allure.epic("Narrative Delivery")
@allure.feature("Prompt consumer-seam contract")
class TestActorPromptMemoryRelevance:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("language", ["English", "Russian"])
    @allure.story("Actor memory prompt")
    @allure.title("Actor prompt receives relevant memories and excludes unrelated fallback")
    async def test_actor_prompt_receives_relevant_memories_in_both_locales(self, language: str) -> None:
        state, npc = _build_actor_state()
        client = kwargs_mod.make_mock_llm(kwargs_mod.ACTOR_REPLY_JSON)
        actor = Actor(
            llm_client=client,
            npc=npc,
            knowledge_query=KnowledgeQueryEngine(state.knowledge_graph),
            language=language,
        )

        await actor.act(
            input_data="Do you remember me?",
            context={"game_state": state, "location_name": "the gate"},
        )

        captured = kwargs_mod.capture_system_prompt(client)
        assert _RELEVANT_TEXT in captured
        assert _IRRELEVANT_TEXT not in captured

    @pytest.mark.asyncio
    @pytest.mark.parametrize("language", ["English", "Russian"])
    @allure.story("Actor memory prompt")
    @allure.title("Actor action prompt receives active-goal target memories in both locales")
    async def test_actor_action_prompt_receives_goal_target_memories_in_both_locales(self, language: str) -> None:
        state, npc = _build_actor_state_with_goal()
        client = kwargs_mod.make_mock_llm(_ACTION_REPLY_JSON)
        actor = Actor(
            llm_client=client,
            npc=npc,
            knowledge_query=KnowledgeQueryEngine(state.knowledge_graph),
            language=language,
        )

        await actor.act(
            input_data="Choose your next action.",
            context={
                "game_state": state,
                "goal_target_name": "Marcus",
                "is_npc_turn": True,
                "location_name": "the gate",
            },
        )

        captured = kwargs_mod.capture_system_prompt(client)
        assert _TARGET_TEXT in captured
        assert _IRRELEVANT_TEXT not in captured

    @pytest.mark.asyncio
    @allure.story("Actor memory prompt")
    @allure.title("Actor prompt receives memories selected by concept tags")
    async def test_actor_prompt_receives_concept_tag_memories(self) -> None:
        state, npc = _build_actor_state_with_concept_memory()
        client = kwargs_mod.make_mock_llm(kwargs_mod.ACTOR_REPLY_JSON)
        actor = Actor(
            llm_client=client,
            npc=npc,
            knowledge_query=KnowledgeQueryEngine(state.knowledge_graph),
        )

        await actor.act(
            input_data="Have you seen anything like this light?",
            context={
                "memory_concept_tags": ["light_without_fire"],
                "location_name": "the gate",
            },
        )

        captured = kwargs_mod.capture_system_prompt(client)
        assert _CONCEPT_TEXT in captured
        assert _RELEVANT_TEXT not in captured
        assert _IRRELEVANT_TEXT not in captured

    @pytest.mark.asyncio
    @allure.story("Actor memory prompt")
    @allure.title("Actor prompt clears a stale memory section when a later turn has no memories")
    async def test_actor_prompt_does_not_reuse_stale_memories_after_memory_is_removed(self) -> None:
        state, npc = _build_actor_state_without_fallback()
        client = kwargs_mod.make_mock_llm(kwargs_mod.ACTOR_REPLY_JSON)
        actor = Actor(
            llm_client=client,
            npc=npc,
            knowledge_query=KnowledgeQueryEngine(state.knowledge_graph),
        )

        await actor.act(
            input_data="Do you remember me?",
            context={"game_state": state, "location_name": "the gate"},
        )
        assert _RELEVANT_TEXT in kwargs_mod.capture_system_prompt(client)

        memory_id = next(node.uuid for node in state.knowledge_graph.all_nodes() if node.text == _RELEVANT_TEXT)
        state.knowledge_graph.remove_node(memory_id)
        await actor.act(
            input_data="What else do you remember?",
            context={"game_state": state, "location_name": "the gate"},
        )

        captured = kwargs_mod.capture_system_prompt(client)
        assert _RELEVANT_TEXT not in captured
