"""PlanExecutor ↔ NPCTicker integration tests.

These exercise the new deterministic NPC departure step added in
PR B (NPC Autonomy). The ticker runs *after*
:meth:`PlanExecutor._resolve_npc_turns` and *before*
:meth:`PlanExecutor._advance_world_state`, so a populated
``raw_outputs.npc_departures`` list reaches both the World Chronicler
(for prompt context) and the Narrator (for the player-facing prose).
"""

from __future__ import annotations

from functools import partial
from unittest.mock import AsyncMock

import allure
import pytest

from cast import director_dialogue, director_events, director_execution, director_retaliation, npc_ticker, npc_turn
from cast.director import DirectorCast
from cast.schemas import chronicler_response as chronicler_schema, turn_outputs
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


def _register_into(gs: gs_mod.GameState, card: NPCCard) -> None:
    """Module-level registrar used as PlanExecutor.register_npc_fn.

    The old fixture passed ``lambda npc: None``, which silently hid
    every freshly-generated NPCCard from ``gs.npcs`` — which in turn
    made ``NPCTicker._classify`` short-circuit on every same-turn
    generation path and rendered the skip_uuids feature untestable.
    """
    gs.npcs[card.uuid] = card


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
    executor = director_execution.PlanExecutor(
        gs,
        agents,
        cast_obj,
        register_npc_fn=partial(_register_into, gs),
    )
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
        outputs_sent: turn_outputs.TurnOutputs = narrator.execute.call_args.kwargs["input_data"]
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

        outputs_sent: turn_outputs.TurnOutputs = narrator.execute.call_args.kwargs["input_data"]
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
        outputs_sent: turn_outputs.TurnOutputs = narrator.execute.call_args.kwargs["input_data"]
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
        outputs_sent: turn_outputs.TurnOutputs = chronicler.execute.call_args.kwargs["input_data"]
        assert len(outputs_sent.npc_departures) == 1
        assert "Lucia" in outputs_sent.npc_departures[0]


@allure.epic("NPC Interaction")
@allure.feature("NPC autonomy wiring")
class TestPlanExecutorSameTurnEvictionSkip:
    """Verify the ticker does not evict NPCs generated this very turn."""

    @allure.story("Same-turn generation skip")
    @allure.title("A bartender generated this turn is NOT evicted by a morning-tavern rebuild")
    @pytest.mark.asyncio
    async def test_same_turn_generated_npc_not_evicted(self):
        executor, gs, narrator, _chronicler = _build_executor(game_time="morning")

        # Scene builder returns a scene with a shell SceneNPC (no uuid).
        # init_scene_npcs will back it with the NPCCard the generator
        # returns, matching the real runtime flow.
        scene = scene_mod.Scene(
            location_id="tavern",
            description="The Rusty Anchor, mid-morning.",
            npcs_present=[scene_mod.SceneNPC(role="bartender")],
        )
        executor._cast.scene_builder.execute = AsyncMock(return_value=scene)
        marco = NPCCard(name="Marco", occupation="bartender")
        executor._cast.npc_generator.execute = AsyncMock(return_value=[marco])

        await executor.execute_plan(
            plan={"action_type": "EXPLORE", "delegate_to": ["scene_builder"], "targets": []},
            player_action="step into the tavern",
            completed_events=[],
        )

        # Marco must survive — he was generated *this* turn.
        assert len(scene.npcs_present) == 1
        assert scene.npcs_present[0].uuid == marco.uuid
        outputs_sent: turn_outputs.TurnOutputs = narrator.execute.call_args.kwargs["input_data"]
        assert outputs_sent.npc_departures == []
        # Sanity: the NPCCard also made it into the game state via the
        # real registrar — if this fails the fixture is broken, not the
        # feature under test.
        assert gs.npcs[marco.uuid] is marco

    @allure.story("Same-turn generation skip")
    @allure.title("A pre-existing absent NPC is still evicted during a scene rebuild")
    @pytest.mark.asyncio
    async def test_scene_rebuild_still_evicts_pre_existing_absent_npc(self):
        # This is the regression partner to the test above: `skip_uuids`
        # must shield *only* the NPCs generated this turn, not every NPC
        # in the scene. An already-registered guard standing in a night
        # tavern should still get evicted by the schedule.
        executor, gs, narrator, _chronicler = _build_executor(game_time="night")
        lucia = _register_npc(gs, _GUARD_UUID, "Lucia", "guard")
        assert lucia.occupation == "guard"

        # Scene rebuilds to include the existing guard (pre-initialised
        # SceneNPC, carries her uuid) plus a fresh bartender shell.
        scene = scene_mod.Scene(
            location_id="tavern",
            description="The Rusty Anchor after dark.",
            npcs_present=[
                scene_mod.SceneNPC(role="guard", uuid=_GUARD_UUID),
                scene_mod.SceneNPC(role="bartender"),
            ],
        )
        executor._cast.scene_builder.execute = AsyncMock(return_value=scene)
        marco = NPCCard(name="Marco", occupation="bartender")
        executor._cast.npc_generator.execute = AsyncMock(return_value=[marco])

        await executor.execute_plan(
            plan={"action_type": "EXPLORE", "delegate_to": ["scene_builder"], "targets": []},
            player_action="walk into the tavern",
            completed_events=[],
        )

        # Marco (new this turn) stays; Lucia (pre-existing) gets evicted.
        remaining_uuids = [snpc.uuid for snpc in scene.npcs_present]
        assert marco.uuid in remaining_uuids
        assert _GUARD_UUID not in remaining_uuids
        outputs_sent: turn_outputs.TurnOutputs = narrator.execute.call_args.kwargs["input_data"]
        assert len(outputs_sent.npc_departures) == 1
        assert "Lucia" in outputs_sent.npc_departures[0]
