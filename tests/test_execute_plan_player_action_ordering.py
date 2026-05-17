"""Regression tests for the player-action position in the scene action log.

Consumer-seam coverage for PR #191 review findings C1–C4 + the
first-turn edge case:

* C1 — the player's action must be appended to ``scene_action_log``
  *before* the same turn's NPC reactions resolve, so an NPC reading
  ``THIS SCENE SO FAR`` next turn sees the utterance it reacted to
  ahead of its own reaction.
* C2 — on a scene-changing turn the triggering player action must be
  consolidated with the *outgoing* scene and must not leak into the
  new scene's empty log.
* C3 — an aggressive player action must reach the scene log flagged
  ``significant`` (the ``is_aggressive`` flag must be threaded through
  the real consumer path, not just the ``append_player_action`` helper).
* First turn — when there is no outgoing scene the player's action must
  survive the scene build (the log clear must be coupled to having
  actually consolidated something).
* C4 — a consolidation failure must not lose the turn and must still
  clear the log (otherwise the next swap re-consolidates and
  double-writes).

These drive the real :meth:`PlanExecutor.execute_plan`; only
collaborators irrelevant to log ordering are stubbed.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import allure
import pytest

from cast import director_execution
from knowledge.graph import KnowledgeGraph
from knowledge.memory import MemoryManager
from models import (
    game_state as gs_mod,
    npc_card as npc_mod,
    scene as scene_mod,
    scene_action_log as sal_mod,
    setting as setting_mod,
)
from tests._uuid_helpers import make_uuid

ActorKind = sal_mod.ActorKind
SceneActionEntry = sal_mod.SceneActionEntry
GameState = gs_mod.GameState
Scene = scene_mod.Scene
SceneNPC = scene_mod.SceneNPC

_NPC_UUID = make_uuid("npc-marcus")
_OLD_LOC = make_uuid("loc-old")
_NEW_LOC = make_uuid("loc-new")

pytestmark = [
    allure.epic("NPC short-term memory"),
    allure.feature("Scene action log ordering"),
]


class _NpcTurnRecorder:
    """Stand-in for ``_resolve_npc_turns`` recording the log at call time."""

    def __init__(self, game_state: GameState) -> None:
        self._gs = game_state
        self.kinds_at_call: list[list] = []

    async def __call__(self, *_args, **_kwargs) -> None:
        self.kinds_at_call.append([entry.actor_kind for entry in self._gs.scene_action_log])
        self._gs.scene_action_log.append(
            SceneActionEntry(
                actor_kind=ActorKind.NPC,
                actor_uuid=_NPC_UUID,
                actor_name="Marcus",
                action_type="TALK",
                description="Marcus nods.",
                game_clock=self._gs.game_clock,
            ),
        )


class _ConsolidateSpy:
    """Capture the entries handed to ``consolidate_scene``."""

    def __init__(self) -> None:
        self.entries: list = []

    async def __call__(self, _manager, request) -> None:
        self.entries = list(request.entries)


async def _raise_llm_timeout(_manager, _request) -> None:
    raise RuntimeError("LLM timeout")


def _make_gs(*, with_scene: bool) -> GameState:
    gs = GameState(
        setting=setting_mod.Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=KnowledgeGraph(),
    )
    marcus = npc_mod.NPCCard(name="Marcus", occupation="guard")
    marcus.uuid = _NPC_UUID
    gs.npcs[_NPC_UUID] = marcus
    if with_scene:
        gs.current_scene = Scene(
            location_id=_OLD_LOC,
            description="The old marketplace.",
            npcs_present=[SceneNPC(role="guard", uuid=_NPC_UUID)],
        )
    return gs


def _make_executor(gs: GameState, monkeypatch) -> director_execution.PlanExecutor:
    executor = director_execution.PlanExecutor(
        game_state=gs,
        events=AsyncMock(),
        event_manager=AsyncMock(),
        dialogue=AsyncMock(),
        retaliation=AsyncMock(),
        npc_turns=AsyncMock(),
        npc_ticker=AsyncMock(),
        memory_manager=AsyncMock(spec=MemoryManager),
        scene_builder=AsyncMock(),
        narrator=AsyncMock(),
        npc_generator=AsyncMock(),
        data_miner=AsyncMock(),
        item_generator=AsyncMock(),
    )
    # Stub collaborators irrelevant to log-ordering so the real
    # execute_plan / _prepare_scene path runs without external I/O.
    monkeypatch.setattr(executor, "_process_events", AsyncMock(return_value=[]))
    monkeypatch.setattr(executor, "_process_target_npcs", AsyncMock(return_value=set()))
    monkeypatch.setattr(executor, "_run_action_handler", AsyncMock())
    monkeypatch.setattr(executor, "_narrate_and_review", AsyncMock(return_value="narrated"))
    monkeypatch.setattr(executor._npc_ticker, "tick", Mock())
    monkeypatch.setattr(executor._events, "propagate_rumors_for_turn", Mock())
    monkeypatch.setattr(executor._dialogue, "init_scene_npcs", AsyncMock(return_value=[]))
    return executor


def _plan(action_type: str, *, is_aggressive: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        intent=action_type.lower(),
        action_type=action_type,
        is_aggressive=is_aggressive,
        targets=[],
        delegate_to=[],
    )


@allure.story("Ordering")
@allure.title("C1 — player action is logged before the same turn's NPC reactions")
@pytest.mark.asyncio
async def test_player_action_logged_before_npc_turns(monkeypatch) -> None:
    gs = _make_gs(with_scene=True)
    executor = _make_executor(gs, monkeypatch)
    recorder = _NpcTurnRecorder(gs)
    monkeypatch.setattr(executor, "_resolve_npc_turns", recorder)

    await executor.execute_plan(_plan("TALK"), "I greet Marcus.", [])

    assert recorder.kinds_at_call == [[ActorKind.PLAYER]], "NPC turns ran before the player entry was logged"
    kinds = [entry.actor_kind for entry in gs.scene_action_log]
    assert kinds == [ActorKind.PLAYER, ActorKind.NPC]
    assert gs.scene_action_log[0].description == "I greet Marcus."


@allure.story("Significance")
@allure.title("C3 — aggressive player action reaches the log flagged significant")
@pytest.mark.asyncio
async def test_aggressive_player_action_is_significant(monkeypatch) -> None:
    gs = _make_gs(with_scene=True)
    executor = _make_executor(gs, monkeypatch)

    await executor.execute_plan(_plan("OTHER", is_aggressive=True), "I punch Marcus.", [])

    player_entries = [entry for entry in gs.scene_action_log if entry.actor_kind == ActorKind.PLAYER]
    assert len(player_entries) == 1
    entry = player_entries[0]
    assert entry.metadata.get("player_is_aggressive") is True
    assert entry.significant is True


@allure.story("Scene swap")
@allure.title("C2 — scene-change trigger action is consolidated with the outgoing scene, not leaked")
@pytest.mark.asyncio
async def test_scene_change_consolidates_player_trigger_action(monkeypatch) -> None:
    gs = _make_gs(with_scene=True)
    executor = _make_executor(gs, monkeypatch)
    new_scene = Scene(location_id=_NEW_LOC, description="A new road.", npcs_present=[])
    executor._scene_builder.execute = AsyncMock(return_value=new_scene)
    spy = _ConsolidateSpy()
    monkeypatch.setattr("knowledge.scene_consolidation.consolidate_scene", spy)

    await executor.execute_plan(_plan("MOVE"), "I leave for the road.", [])

    assert any(
        entry.actor_kind == ActorKind.PLAYER and entry.description == "I leave for the road." for entry in spy.entries
    ), "player's MOVE trigger was not consolidated with the outgoing scene"
    assert gs.current_scene is new_scene
    assert all(entry.description != "I leave for the road." for entry in gs.scene_action_log), (
        "stale player action leaked into the new scene's log"
    )


@allure.story("First turn")
@allure.title("First turn — player action survives the initial scene build (no outgoing scene)")
@pytest.mark.asyncio
async def test_first_turn_player_action_survives_scene_build(monkeypatch) -> None:
    gs = _make_gs(with_scene=False)
    executor = _make_executor(gs, monkeypatch)
    new_scene = Scene(location_id=_NEW_LOC, description="A clearing.", npcs_present=[])
    executor._scene_builder.execute = AsyncMock(return_value=new_scene)

    await executor.execute_plan(_plan("MOVE"), "I step into the clearing.", [])

    player_entries = [entry for entry in gs.scene_action_log if entry.actor_kind == ActorKind.PLAYER]
    assert [entry.description for entry in player_entries] == ["I step into the clearing."]


@allure.story("Resilience")
@allure.title("C4 — consolidation failure does not lose the turn and still clears the log")
@pytest.mark.asyncio
async def test_consolidation_failure_does_not_lose_turn(monkeypatch, loguru_sink) -> None:
    gs = _make_gs(with_scene=True)
    executor = _make_executor(gs, monkeypatch)
    new_scene = Scene(location_id=_NEW_LOC, description="A new road.", npcs_present=[])
    executor._scene_builder.execute = AsyncMock(return_value=new_scene)
    monkeypatch.setattr("knowledge.scene_consolidation.consolidate_scene", _raise_llm_timeout)

    result = await executor.execute_plan(_plan("MOVE"), "I leave for the road.", [])

    assert result == "narrated"
    assert gs.current_scene is new_scene
    assert all(entry.description != "I leave for the road." for entry in gs.scene_action_log)
    assert any(rec["level"].name == "ERROR" for rec in loguru_sink)
