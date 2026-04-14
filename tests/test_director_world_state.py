"""PlanExecutor ↔ WorldChronicler wiring tests.

These exercise the gate in
:meth:`cast.director_execution.PlanExecutor.execute_plan`: the
chronicler only runs when (1) a scene was built this turn and
(2) the cast has a ``world_chronicler`` wired. On a miss, the
applier is skipped entirely and parity with PR-less behaviour is
preserved.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast import director_dialogue, director_events, director_execution, director_retaliation, npc_ticker, npc_turn
from cast.director import DirectorCast
from cast.schemas import chronicler_response as chronicler_schema
from knowledge import graph as graph_mod, memory as memory_mod
from models import game_state as gs_mod, scene as scene_mod, setting as setting_mod, world_state as world_state_mod
from timeline.event_manager import EventManager


def _make_plan_executor_pieces(*, with_chronicler: bool):
    setting = setting_mod.Setting(name="Rome", time_period="1 AD", region="Italy", summary="")
    gs = gs_mod.GameState(setting=setting, knowledge_graph=graph_mod.KnowledgeGraph())
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
        memory_manager=mem_mgr,
    )

    narrator = AsyncMock()
    narrator.execute = AsyncMock(return_value="Narrated.")
    scene_builder = AsyncMock()
    scene_builder.execute = AsyncMock(
        return_value=scene_mod.Scene(
            location_id="forum",
            description="The bustling Forum.",
            npcs_present=[],
        ),
    )
    npc_generator = AsyncMock()
    npc_generator.execute = AsyncMock(return_value=[])

    chronicler: AsyncMock | None = AsyncMock() if with_chronicler else None
    if chronicler is not None:
        chronicler.execute = AsyncMock(
            return_value=chronicler_schema.ChroniclerResponse(
                new_threads=[
                    chronicler_schema.WorldThreadDraft(
                        description="Rumours of a senator poisoning",
                        category="political",
                    ),
                ],
                thread_updates=[],
                scheduled_events=[
                    chronicler_schema.ScheduledEventDraft(
                        name="Courier arrives with news",
                        hours_from_now=4.0,
                        location_id="forum",
                        scope="remote",
                        on_complete_description="A courier bursts in with sealed dispatches.",
                    ),
                ],
                world_mood="tense, watchful",
            ),
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
    return executor, gs, chronicler, event_mgr


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("World Chronicler wiring")
class TestPlanExecutorChroniclerGate:
    @allure.story("Chronicler gate")
    @allure.title("PlanExecutor applies ChroniclerResponse when a scene was built and a chronicler is wired")
    @pytest.mark.asyncio
    async def test_chronicler_applied_on_new_scene(self):
        executor, gs, chronicler, event_mgr = _make_plan_executor_pieces(with_chronicler=True)

        await executor.execute_plan(
            plan={"action_type": "EXPLORE", "delegate_to": ["scene_builder"]},
            player_action="explore the forum",
            completed_events=[],
        )

        assert chronicler is not None
        chronicler.execute.assert_awaited_once()
        assert len(gs.world_state.threads) == 1
        assert gs.world_state.threads[0].description == "Rumours of a senator poisoning"
        assert gs.world_state.threads[0].introduced_scene == gs.scene_number
        assert gs.world_state.threads[0].last_advanced_scene == gs.scene_number
        assert gs.world_state.world_mood == "tense, watchful"
        assert gs.world_state.last_chronicled_scene == gs.scene_number
        pending = event_mgr.get_pending_events()
        assert any(ev.name == "Courier arrives with news" for ev in pending)

    @allure.story("Chronicler gate")
    @allure.title("PlanExecutor skips the chronicler entirely when world_chronicler is None")
    @pytest.mark.asyncio
    async def test_chronicler_skipped_when_absent(self):
        executor, gs, _unused, _event_mgr = _make_plan_executor_pieces(with_chronicler=False)

        await executor.execute_plan(
            plan={"action_type": "EXPLORE", "delegate_to": ["scene_builder"]},
            player_action="explore the forum",
            completed_events=[],
        )

        assert gs.world_state.threads == []
        assert gs.world_state.world_mood is None
        assert gs.world_state.last_chronicled_scene == 0

    @allure.story("Chronicler gate")
    @allure.title("PlanExecutor does NOT call the chronicler on a CONTINUATION turn with no new scene")
    @pytest.mark.asyncio
    async def test_chronicler_not_called_on_continuation(self):
        executor, gs, chronicler, _event_mgr = _make_plan_executor_pieces(with_chronicler=True)

        # TALK is not a scene-changing action, so PlanExecutor.execute_plan
        # never builds a scene and the chronicler gate should short-circuit.
        await executor.execute_plan(
            plan={"action_type": "TALK", "delegate_to": ["actor"], "targets": []},
            player_action="greet the guard",
            completed_events=[],
        )

        assert chronicler is not None
        chronicler.execute.assert_not_awaited()
        assert gs.world_state.threads == []
        assert gs.world_state.last_chronicled_scene == 0


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("World Chronicler wiring")
class TestApplyThreadUpdates:
    @allure.story("Thread updates")
    @allure.title("_apply_thread_updates bumps last_advanced_scene and honours status changes by UUID")
    def test_apply_thread_updates_matches_by_uuid(self):
        thread_a = world_state_mod.WorldThread(description="A", category="political", introduced_scene=1)
        thread_b = world_state_mod.WorldThread(description="B", category="social", introduced_scene=1)
        state = world_state_mod.WorldState(threads=[thread_a, thread_b])
        updates = [
            chronicler_schema.WorldThreadUpdate(thread_uuid=thread_a.uuid, status="resolved"),
            chronicler_schema.WorldThreadUpdate(thread_uuid=thread_b.uuid),
        ]
        director_execution._apply_thread_updates(state, updates, current_scene=5)

        assert thread_a.status == "resolved"
        assert thread_a.last_advanced_scene == 5
        assert thread_b.status == "open"
        assert thread_b.last_advanced_scene == 5

    @allure.story("Thread updates")
    @allure.title("_apply_thread_updates silently ignores updates whose UUID does not match any thread")
    def test_apply_thread_updates_ignores_unknown_uuid(self):
        thread = world_state_mod.WorldThread(description="A", category="political", introduced_scene=1)
        state = world_state_mod.WorldState(threads=[thread])
        updates = [chronicler_schema.WorldThreadUpdate(thread_uuid="does-not-exist", status="resolved")]
        director_execution._apply_thread_updates(state, updates, current_scene=7)

        assert thread.status == "open"
        assert thread.last_advanced_scene == 0
