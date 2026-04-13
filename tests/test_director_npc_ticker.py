"""PlanExecutor ↔ NPCTicker integration tests.

These exercise the new deterministic NPC departure step added in
PR B (NPC Autonomy). The ticker runs *after*
:meth:`PlanExecutor._resolve_npc_turns` and *before*
:meth:`PlanExecutor._advance_world_state`, so a populated
``raw_outputs.npc_departures`` list reaches both the World Chronicler
(for prompt context) and the Narrator (for the player-facing prose).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast import director_dialogue, director_events, director_execution, director_retaliation, npc_ticker, npc_turn
from cast.director import DirectorCast
from cast.schemas import chronicler_response as chronicler_schema
from cast.schemas.turn_outputs import TurnOutputs
from knowledge import graph as graph_mod, memory as memory_mod
from models import game_state as gs_mod, scene as scene_mod, setting as setting_mod
from models.npc_card import NPCCard
from timeline.event_manager import EventManager

_BARTENDER_UUID = "npc-bartender"
_GUARD_UUID = "npc-guard"


def _register_npc(gs: gs_mod.GameState, uuid: str, name: str, occupation: str) -> NPCCard:
    npc = NPCCard(name=name, occupation=occupation)
    npc.uuid = uuid
    gs.npcs[uuid] = npc
    return npc


def _build_executor(*, game_time: str, with_chronicler: bool = False):
    setting = setting_mod.Setting(name="Rome", time_period="1 AD", region="Italy", summary="")
    gs = gs_mod.GameState(setting=setting, knowledge_graph=graph_mod.KnowledgeGraph())
    gs.game_time = game_time
    event_mgr = EventManager(game_state=gs, knowledge_graph=gs.knowledge_graph)
    mem_mgr = memory_mod.MemoryManager.__new__(memory_mod.MemoryManager)
    events = director_events.EventProcessor(gs, event_mgr, mem_mgr)
    actors: dict[str, object] = {}
    dialogue = director_dialogue.DialogueHandler(gs, actors, mem_mgr)
    retaliation = director_retaliation.RetaliationHandler(gs, actors)
    npc_turns = npc_turn.NPCTurnResolver(gs, actors)
    ticker = npc_ticker.NPCTicker(gs)
    agents = director_execution._Agents(
        events=events,
        dialogue=dialogue,
        retaliation=retaliation,
        npc_turns=npc_turns,
        npc_ticker=ticker,
    )

    narrator = AsyncMock()
    narrator.execute = AsyncMock(return_value="Narrated.")
    scene_builder = AsyncMock()
    npc_generator = AsyncMock()
    npc_generator.execute = AsyncMock(return_value=[])

    chronicler: AsyncMock | None = AsyncMock() if with_chronicler else None
    if chronicler is not None:
        chronicler.execute = AsyncMock(
            return_value=chronicler_schema.ChroniclerResponse(),
        )

    cast_obj = DirectorCast(
        scene_builder=scene_builder,
        narrator=narrator,
        npc_generator=npc_generator,
        data_miner=AsyncMock(),
        item_generator=None,
        world_chronicler=chronicler,
    )
    executor = director_execution.PlanExecutor(gs, agents, cast_obj, register_npc_fn=lambda npc: None)
    return executor, gs, narrator, chronicler


def _seed_tavern_scene(gs: gs_mod.GameState, *npc_uuids: str) -> scene_mod.Scene:
    scene = scene_mod.Scene(
        location_id="tavern",
        description="The Rusty Anchor tavern.",
        npcs_present=[scene_mod.SceneNPC(role="npc", uuid=uid) for uid in npc_uuids],
    )
    gs.current_scene = scene
    return scene


@allure.epic("NPC Interaction")
@allure.feature("NPC autonomy wiring")
class TestPlanExecutorTickerGate:
    @allure.story("Ticker gate")
    @allure.title("PlanExecutor populates npc_departures with schedule-evicted NPCs on a TALK turn")
    @pytest.mark.asyncio
    async def test_bartender_evicted_on_talk_in_morning(self):
        executor, gs, narrator, _chronicler = _build_executor(game_time="morning")
        _register_npc(gs, _BARTENDER_UUID, "Marco", "bartender")
        scene = _seed_tavern_scene(gs, _BARTENDER_UUID)

        await executor.execute_plan(
            plan={"action_type": "TALK", "delegate_to": [], "targets": []},
            player_action="look around the tavern",
            completed_events=[],
        )

        assert scene.npcs_present == []
        narrator.execute.assert_awaited_once()
        outputs_sent: TurnOutputs = narrator.execute.call_args.kwargs["input_data"]
        assert len(outputs_sent.npc_departures) == 1
        assert outputs_sent.npc_departures[0].startswith("Marco (bartender)")

    @allure.story("Ticker gate")
    @allure.title("PlanExecutor skips the ticker entirely when there is no current scene")
    @pytest.mark.asyncio
    async def test_ticker_skipped_without_scene(self):
        executor, gs, narrator, _chronicler = _build_executor(game_time="morning")
        _register_npc(gs, _BARTENDER_UUID, "Marco", "bartender")
        # No scene set up — current_scene is None.
        assert gs.current_scene is None

        await executor.execute_plan(
            plan={"action_type": "TALK", "delegate_to": [], "targets": []},
            player_action="shout into the void",
            completed_events=[],
        )

        outputs_sent: TurnOutputs = narrator.execute.call_args.kwargs["input_data"]
        assert outputs_sent.npc_departures == []

    @allure.story("Ticker gate")
    @allure.title("PlanExecutor leaves the scene untouched when no NPC's schedule says 'absent'")
    @pytest.mark.asyncio
    async def test_no_departures_when_all_present(self):
        executor, gs, narrator, _chronicler = _build_executor(game_time="morning")
        _register_npc(gs, _GUARD_UUID, "Lucia", "guard")  # day-shift, present in morning
        scene = _seed_tavern_scene(gs, _GUARD_UUID)

        await executor.execute_plan(
            plan={"action_type": "TALK", "delegate_to": [], "targets": []},
            player_action="look around",
            completed_events=[],
        )

        assert [snpc.uuid for snpc in scene.npcs_present] == [_GUARD_UUID]
        outputs_sent: TurnOutputs = narrator.execute.call_args.kwargs["input_data"]
        assert outputs_sent.npc_departures == []

    @allure.story("Ticker gate")
    @allure.title("WorldChronicler sees npc_departures in the TurnOutputs it receives")
    @pytest.mark.asyncio
    async def test_chronicler_sees_departures(self):
        executor, gs, _narrator, chronicler = _build_executor(
            game_time="night",
            with_chronicler=True,
        )
        _register_npc(gs, _GUARD_UUID, "Lucia", "guard")
        # Force raw_outputs.scene to be set so the chronicler gate opens; we do
        # this by asking the mocked scene_builder to return a scene with the
        # existing guard still in it and running an EXPLORE action.
        scene = _seed_tavern_scene(gs, _GUARD_UUID)
        executor._cast.scene_builder.execute = AsyncMock(return_value=scene)

        await executor.execute_plan(
            plan={"action_type": "EXPLORE", "delegate_to": ["scene_builder"], "targets": []},
            player_action="look around",
            completed_events=[],
        )

        assert chronicler is not None
        chronicler.execute.assert_awaited_once()
        outputs_sent: TurnOutputs = chronicler.execute.call_args.kwargs["input_data"]
        assert len(outputs_sent.npc_departures) == 1
        assert "Lucia" in outputs_sent.npc_departures[0]
