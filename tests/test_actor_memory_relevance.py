"""Tests for Actor-side memory relevance selection."""

from __future__ import annotations

import allure

from cast.actor_memory import select_actor_memories
from knowledge.graph import KnowledgeGraph
from knowledge.node import EdgeType, KnowledgeNode, KnowledgeScope, KnowledgeSource
from knowledge.query import KnowledgeQueryEngine
from models.game_state import GameState, PlayerState
from models.goal import Goal, GoalKind, GoalStatus
from models.npc_card import NPCCard
from models.setting import Setting
from tests._uuid_helpers import make_uuid

_ACTOR_ID = make_uuid("actor-memory-actor")
_PLAYER_ID = make_uuid("actor-memory-player")
_TARGET_ID = make_uuid("actor-memory-target")
_OTHER_ID = make_uuid("actor-memory-other")


def _state_with_actor() -> tuple[GameState, NPCCard, KnowledgeGraph]:
    graph = KnowledgeGraph()
    graph.register_actor_node(_ACTOR_ID, label="Aulus")
    actor = NPCCard(
        uuid=_ACTOR_ID,
        name="Aulus",
        occupation="guard",
        biography="A veteran guard.",
    )
    state = GameState(
        setting=Setting(name="Rome", time_period="AD 64", region="Italia", summary=""),
        knowledge_graph=graph,
        player=PlayerState(uuid=_PLAYER_ID, name="Player"),
        npcs={_ACTOR_ID: actor},
    )
    return state, actor, graph


def _attach_memory(
    graph: KnowledgeGraph,
    text: str,
    *,
    timestamp: float,
    salience: float,
    fields: dict | None = None,
) -> KnowledgeNode:
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
    return memory


@allure.epic("NPC Interaction")
@allure.feature("Actor memory relevance")
class TestActorMemorySelection:
    @allure.story("Dialogue relevance")
    @allure.title("Dialogue memory selection prefers player-subject memories over broad fallback")
    def test_dialogue_prefers_player_subject_memories_over_broad_fallback(self):
        state, actor, graph = _state_with_actor()
        relevant = _attach_memory(
            graph,
            "The player spared Aulus at the gate.",
            timestamp=1.0,
            salience=0.1,
            fields={"subject_id": state.player.uuid},
        )
        for idx in range(5):
            _attach_memory(
                graph,
                "Unrelated market memory {0}".format(idx),
                timestamp=10.0 + idx,
                salience=1.0,
                fields={"subject_id": _OTHER_ID},
            )

        selected = select_actor_memories(actor, KnowledgeQueryEngine(graph), {"game_state": state})

        assert [memory.uuid for memory in selected] == [relevant.uuid]

    @allure.story("Autonomous relevance")
    @allure.title("Autonomous turns include memories about the active goal target")
    def test_autonomous_turn_includes_active_goal_target_memories(self):
        state, actor, graph = _state_with_actor()
        actor.tactical_goal = Goal(
            kind=GoalKind.PURSUE,
            description="Watch Marcus.",
            target_uuid=_TARGET_ID,
            status=GoalStatus.ACTIVE,
        )
        target_memory = _attach_memory(
            graph,
            "Marcus bribed a guard yesterday.",
            timestamp=2.0,
            salience=0.2,
            fields={"subject_id": _TARGET_ID},
        )
        _attach_memory(
            graph,
            "The player asked about directions.",
            timestamp=3.0,
            salience=1.0,
            fields={"subject_id": state.player.uuid},
        )

        selected = select_actor_memories(
            actor,
            KnowledgeQueryEngine(graph),
            {"game_state": state, "is_npc_turn": True},
        )

        selected_ids = {memory.uuid for memory in selected}
        assert target_memory.uuid in selected_ids

    @allure.story("Concept relevance")
    @allure.title("Concept tags add matches, dedupe duplicate memories, and cap the result at five")
    def test_concept_tags_add_matches_dedupe_and_cap_to_five(self):
        state, actor, graph = _state_with_actor()
        duplicate = _attach_memory(
            graph,
            "The player used light without flame.",
            timestamp=20.0,
            salience=0.9,
            fields={
                "subject_id": state.player.uuid,
                "tags": ["light_without_flame"],
            },
        )
        for idx in range(6):
            _attach_memory(
                graph,
                "Concept memory {0}".format(idx),
                timestamp=float(idx),
                salience=0.8,
                fields={"tags": ["light_without_flame"]},
            )

        selected = select_actor_memories(
            actor,
            KnowledgeQueryEngine(graph),
            {"game_state": state, "memory_concept_tags": ["light_without_fire"]},
        )

        selected_ids = [memory.uuid for memory in selected]
        assert len(selected_ids) == 5
        assert len(selected_ids) == len(set(selected_ids))
        assert selected_ids.count(duplicate.uuid) == 1

    @allure.story("Fallback")
    @allure.title("Broad held-memory fallback runs only when scoped matches are empty")
    def test_fallback_to_get_memories_held_by_only_when_scoped_matches_empty(self):
        state, actor, graph = _state_with_actor()
        fallback = _attach_memory(
            graph,
            "The market burned at dawn.",
            timestamp=10.0,
            salience=1.0,
            fields={"subject_id": _OTHER_ID},
        )
        query = KnowledgeQueryEngine(graph)

        assert [memory.uuid for memory in select_actor_memories(actor, query, {"game_state": state})] == [
            fallback.uuid,
        ]

        relevant = _attach_memory(
            graph,
            "The player returned the stolen purse.",
            timestamp=1.0,
            salience=0.1,
            fields={"subject_id": state.player.uuid},
        )

        selected = select_actor_memories(actor, query, {"game_state": state})
        assert [memory.uuid for memory in selected] == [relevant.uuid]
