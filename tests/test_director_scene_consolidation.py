"""Test that scene swap consolidates the scene action log into long-term memory."""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast import director_execution
from knowledge.graph import KnowledgeGraph
from knowledge.memory import MemoryManager
from models import scene as scene_mod, scene_action_log as scene_action_log_mod
from models.game_state import GameState
from models.npc_card import NPCCard
from models.setting import Setting
from tests._uuid_helpers import make_uuid

ActorKind = scene_action_log_mod.ActorKind
SceneActionEntry = scene_action_log_mod.SceneActionEntry
Scene = scene_mod.Scene
SceneNPC = scene_mod.SceneNPC

_NPC_UUID = make_uuid("npc-marcus")
_OLD_LOC = make_uuid("loc-old")

pytestmark = [
    allure.epic("NPC short-term memory"),
    allure.feature("Scene swap hook"),
]


def _make_gs_with_outgoing_scene() -> GameState:
    gs = GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=KnowledgeGraph(),
    )
    marcus = NPCCard(name="Marcus", occupation="guard")
    marcus.uuid = _NPC_UUID
    gs.npcs[_NPC_UUID] = marcus
    gs.current_scene = Scene(
        location_id=_OLD_LOC,
        description="The old marketplace.",
        npcs_present=[SceneNPC(role="guard", uuid=_NPC_UUID)],
    )
    gs.scene_action_log.append(
        SceneActionEntry(
            actor_kind=ActorKind.PLAYER,
            actor_name="Player",
            action_type="TALK",
            description="I bid Marcus farewell.",
            game_clock=1.0,
        ),
    )
    gs.scene_action_log.append(
        SceneActionEntry(
            actor_kind=ActorKind.NPC,
            actor_uuid=_NPC_UUID,
            actor_name="Marcus",
            action_type="ATTACK",
            description="Marcus draws steel.",
            game_clock=1.5,
            significant=True,
        ),
    )
    return gs


def _make_executor() -> tuple[director_execution.PlanExecutor, GameState, AsyncMock]:
    gs = _make_gs_with_outgoing_scene()
    memory_manager = AsyncMock(spec=MemoryManager)

    executor = director_execution.PlanExecutor(
        game_state=gs,
        events=AsyncMock(),
        event_manager=AsyncMock(),
        dialogue=AsyncMock(),
        retaliation=AsyncMock(),
        npc_turns=AsyncMock(),
        npc_ticker=AsyncMock(),
        memory_manager=memory_manager,
        scene_builder=AsyncMock(),
        narrator=AsyncMock(),
        npc_generator=AsyncMock(),
        data_miner=AsyncMock(),
        item_generator=AsyncMock(),
    )
    return executor, gs, memory_manager


@allure.story("Scene swap")
@allure.title("Outgoing scene's action log is handed to scene_consolidation.consolidate_scene")
@pytest.mark.asyncio
async def test_consolidate_called_on_outgoing_scene(monkeypatch) -> None:
    executor, gs, memory_manager = _make_executor()
    consolidate_spy = AsyncMock(return_value=None)
    monkeypatch.setattr("knowledge.scene_consolidation.consolidate_scene", consolidate_spy)

    outgoing_scene = gs.current_scene
    outgoing_log = list(gs.scene_action_log)

    await executor._consolidate_outgoing_scene(outgoing_scene)

    consolidate_spy.assert_awaited_once()
    await_args = consolidate_spy.await_args
    assert await_args is not None
    passed_manager, passed_request = await_args.args
    assert passed_manager is memory_manager
    assert passed_request.entries == outgoing_log
    assert passed_request.present_npc_uuids == [_NPC_UUID]
    assert passed_request.location_id == _OLD_LOC
    assert passed_request.player_subject_id == gs.player.uuid


@allure.story("Scene swap")
@allure.title("Empty outgoing log is a no-op — consolidate_scene is not called")
@pytest.mark.asyncio
async def test_empty_log_skips_consolidation(monkeypatch) -> None:
    executor, gs, _ = _make_executor()
    consolidate_spy = AsyncMock(return_value=None)
    monkeypatch.setattr("knowledge.scene_consolidation.consolidate_scene", consolidate_spy)
    gs.scene_action_log.clear()

    await executor._consolidate_outgoing_scene(gs.current_scene)

    consolidate_spy.assert_not_awaited()


@allure.story("Scene swap")
@allure.title("None outgoing scene (first turn) is a no-op")
@pytest.mark.asyncio
async def test_none_outgoing_scene_skips_consolidation(monkeypatch) -> None:
    executor, _gs, _ = _make_executor()
    consolidate_spy = AsyncMock(return_value=None)
    monkeypatch.setattr("knowledge.scene_consolidation.consolidate_scene", consolidate_spy)

    await executor._consolidate_outgoing_scene(None)

    consolidate_spy.assert_not_awaited()
