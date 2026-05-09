"""Tests for scene_consolidation.consolidate_scene — scene-end memory persistence."""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from knowledge.graph import KnowledgeGraph
from knowledge.memory import MemoryManager
from knowledge.node import KnowledgeSource
from knowledge.scene_consolidation import SceneConsolidationRequest, consolidate_scene
from llm.message import LLMResponse
from models.scene_action_log import ActorKind, SceneActionEntry
from tests._uuid_helpers import make_uuid

_NPC_ALPHA = make_uuid("npc-alpha")
_NPC_BETA = make_uuid("npc-beta")
_LOC = make_uuid("loc-tavern")
_PLAYER_UUID = make_uuid("player")

pytestmark = [
    allure.epic("NPC short-term memory"),
    allure.feature("Scene-end consolidation"),
]


def _make_manager() -> tuple[MemoryManager, KnowledgeGraph, AsyncMock]:
    graph = KnowledgeGraph()
    llm = AsyncMock()
    llm.send_message = AsyncMock(
        return_value=LLMResponse(body="A heated argument over silver.", model="stub", usage={}),
    )
    return MemoryManager(graph=graph, llm_client=llm), graph, llm


def _routine_entry(actor_name: str, description: str, clock: float = 1.0) -> SceneActionEntry:
    return SceneActionEntry(
        actor_kind=ActorKind.PLAYER if actor_name == "Player" else ActorKind.NPC,
        actor_name=actor_name,
        action_type="TALK",
        description=description,
        game_clock=clock,
    )


def _significant_attack_entry() -> SceneActionEntry:
    return SceneActionEntry(
        actor_kind=ActorKind.NPC,
        actor_uuid=_NPC_ALPHA,
        actor_name="Marcus",
        action_type="ATTACK",
        description="Marcus strikes Livia with a dagger.",
        target_name="Livia",
        game_clock=2.5,
        significant=True,
    )


def _already_persisted_event() -> SceneActionEntry:
    return SceneActionEntry(
        actor_kind=ActorKind.EVENT,
        actor_name="",
        action_type="COMBAT_WITNESS",
        description="A clash already persisted by the combat hook.",
        game_clock=2.6,
        significant=True,
        metadata={"already_persisted": True},
    )


@allure.story("consolidate_scene")
@allure.title("Empty log is a no-op — no LLM calls and no nodes are created")
@pytest.mark.asyncio
async def test_empty_log_no_op() -> None:
    manager, graph, llm = _make_manager()
    await consolidate_scene(
        manager,
        SceneConsolidationRequest(
            entries=[],
            present_npc_uuids=[_NPC_ALPHA],
            game_time=1.0,
            location_id=_LOC,
            player_subject_id=_PLAYER_UUID,
        ),
    )
    llm.send_message.assert_not_awaited()
    assert not graph.all_nodes()


@allure.story("consolidate_scene")
@allure.title("No-present-NPCs short-circuits the call without creating nodes")
@pytest.mark.asyncio
async def test_no_present_npcs_no_op() -> None:
    manager, graph, llm = _make_manager()
    await consolidate_scene(
        manager,
        SceneConsolidationRequest(
            entries=[_routine_entry("Player", "I greet the room.")],
            present_npc_uuids=[],
            game_time=1.0,
            location_id=_LOC,
            player_subject_id=_PLAYER_UUID,
        ),
    )
    llm.send_message.assert_not_awaited()
    assert not graph.all_nodes()


@allure.story("consolidate_scene")
@allure.title("Phase 1 produces one summary memory per present NPC; Phase 2 fires per significant entry")
@pytest.mark.asyncio
async def test_summary_per_npc_plus_significant_node() -> None:
    manager, graph, llm = _make_manager()
    graph.register_actor_node(_NPC_ALPHA, label="Marcus")
    graph.register_actor_node(_NPC_BETA, label="Livia")

    entries = [
        _routine_entry("Player", "I demand the silver back."),
        _routine_entry("Livia", "She refuses."),
        _significant_attack_entry(),
    ]

    await consolidate_scene(
        manager,
        SceneConsolidationRequest(
            entries=entries,
            present_npc_uuids=[_NPC_ALPHA, _NPC_BETA],
            game_time=3.0,
            location_id=_LOC,
            player_subject_id=_PLAYER_UUID,
        ),
    )

    # Phase 1: one summariser LLM call per present NPC.
    assert llm.send_message.await_count == 2
    personal_nodes = [n for n in graph.all_nodes() if n.source == KnowledgeSource.PERSONAL_EXPERIENCE]
    # Two summary nodes (per-NPC) + one significant ATTACK node (shared, witnessed by both).
    assert len(personal_nodes) == 3
    significant = [n for n in personal_nodes if "Marcus strikes Livia" in n.text]
    assert len(significant) == 1


@allure.story("consolidate_scene")
@allure.title("Significant entries flagged already_persisted are NOT duplicated by Phase 2")
@pytest.mark.asyncio
async def test_already_persisted_skipped_in_phase_two() -> None:
    manager, graph, llm = _make_manager()
    graph.register_actor_node(_NPC_ALPHA, label="Marcus")

    entries = [
        _routine_entry("Player", "I look around."),
        _already_persisted_event(),
    ]

    await consolidate_scene(
        manager,
        SceneConsolidationRequest(
            entries=entries,
            present_npc_uuids=[_NPC_ALPHA],
            game_time=3.0,
            location_id=_LOC,
            player_subject_id=_PLAYER_UUID,
        ),
    )

    # Phase 1: one per-NPC summary.
    assert llm.send_message.await_count == 1
    # Phase 2 must skip the already-persisted entry — only the summary node lands.
    personal_nodes = [n for n in graph.all_nodes() if n.source == KnowledgeSource.PERSONAL_EXPERIENCE]
    assert len(personal_nodes) == 1
    assert "A clash already persisted" not in personal_nodes[0].text
