"""PlanExecutor ↔ Dramaturge wiring tests.

These exercise the gate in
:meth:`cast.director_execution.PlanExecutor.execute_plan`: the
Dramaturge only runs when (1) a scene was built this turn and (2) the
cast has a ``dramaturge`` wired. On a miss, the post-Narrator review
is skipped entirely and the Narrator's output is returned unchanged,
preserving parity with the pre-Dramaturge behaviour.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast import director_dialogue, director_events, director_execution, director_retaliation, npc_ticker, npc_turn
from cast.director import DirectorCast
from knowledge.graph import KnowledgeGraph
from knowledge.memory import MemoryManager
from models.game_state import GameState
from models.scene import Scene
from models.setting import Setting
from timeline.event_manager import EventManager


def _make_plan_executor_pieces(*, with_dramaturge: bool):
    setting = Setting(name="Rome", time_period="1 AD", region="Italy", summary="")
    gs = GameState(setting=setting, knowledge_graph=KnowledgeGraph())
    event_mgr = EventManager(game_state=gs, knowledge_graph=gs.knowledge_graph)
    mem_mgr = MemoryManager.__new__(MemoryManager)
    events = director_events.EventProcessor(gs, event_mgr, mem_mgr)
    actors: dict[str, object] = {}
    dialogue = director_dialogue.DialogueHandler(gs, actors, mem_mgr)
    retaliation = director_retaliation.RetaliationHandler(gs, actors)
    npc_turns_resolver = npc_turn.NPCTurnResolver(gs, actors)
    ticker = npc_ticker.NPCTicker(gs)
    agents = director_execution._Agents(
        events=events,
        dialogue=dialogue,
        retaliation=retaliation,
        npc_turns=npc_turns_resolver,
        npc_ticker=ticker,
        memory_manager=mem_mgr,
    )

    narrator = AsyncMock()
    narrator.execute = AsyncMock(return_value="Raw narration.")
    scene_builder = AsyncMock()
    scene_builder.execute = AsyncMock(
        return_value=Scene(
            location_id="forum",
            description="The bustling Forum.",
            npcs_present=[],
        ),
    )
    npc_generator = AsyncMock()
    npc_generator.execute = AsyncMock(return_value=[])

    dramaturge: AsyncMock | None = AsyncMock() if with_dramaturge else None
    if dramaturge is not None:
        dramaturge.execute = AsyncMock(return_value="Corrected narration.")

    cast_obj = DirectorCast(
        scene_builder=scene_builder,
        narrator=narrator,
        npc_generator=npc_generator,
        data_miner=AsyncMock(),
        item_generator=None,
        world_chronicler=None,
        dramaturge=dramaturge,
    )

    executor = director_execution.PlanExecutor(gs, agents, cast_obj, register_npc_fn=lambda npc: None)
    return executor, gs, narrator, dramaturge


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Dramaturge wiring")
class TestPlanExecutorDramaturgeGate:
    @allure.story("Dramaturge gate")
    @allure.title("PlanExecutor calls Dramaturge and returns its corrected narration on a new-scene turn")
    @pytest.mark.asyncio
    async def test_dramaturge_runs_on_new_scene(self):
        executor, _gs, narrator, dramaturge = _make_plan_executor_pieces(with_dramaturge=True)

        result = await executor.execute_plan(
            plan={"action_type": "EXPLORE", "delegate_to": ["scene_builder"]},
            player_action="explore the forum",
            completed_events=[],
        )

        narrator.execute.assert_awaited_once()
        assert dramaturge is not None
        dramaturge.execute.assert_awaited_once()
        assert result == "Corrected narration."

    @allure.story("Dramaturge gate")
    @allure.title("PlanExecutor skips Dramaturge entirely when the cast does not wire one")
    @pytest.mark.asyncio
    async def test_dramaturge_skipped_when_absent(self):
        executor, _gs, narrator, _none = _make_plan_executor_pieces(with_dramaturge=False)

        result = await executor.execute_plan(
            plan={"action_type": "EXPLORE", "delegate_to": ["scene_builder"]},
            player_action="explore the forum",
            completed_events=[],
        )

        narrator.execute.assert_awaited_once()
        assert result == "Raw narration."

    @allure.story("Dramaturge gate")
    @allure.title("PlanExecutor does NOT call Dramaturge on a CONTINUATION turn with no new scene")
    @pytest.mark.asyncio
    async def test_dramaturge_not_called_on_continuation(self):
        executor, _gs, narrator, dramaturge = _make_plan_executor_pieces(with_dramaturge=True)

        result = await executor.execute_plan(
            plan={"action_type": "TALK", "delegate_to": ["actor"], "targets": []},
            player_action="greet the guard",
            completed_events=[],
        )

        narrator.execute.assert_awaited_once()
        assert dramaturge is not None
        dramaturge.execute.assert_not_awaited()
        assert result == "Raw narration."

    @allure.story("Dramaturge gate")
    @allure.title("PlanExecutor returns raw narration when Dramaturge.execute raises unexpectedly")
    @pytest.mark.asyncio
    async def test_dramaturge_exception_falls_back_to_narrator_output(self):
        """Belt-and-braces: even if Dramaturge.act leaks an exception, the player sees the raw narration."""
        executor, _gs, narrator, dramaturge = _make_plan_executor_pieces(with_dramaturge=True)
        assert dramaturge is not None
        dramaturge.execute = AsyncMock(side_effect=RuntimeError("kaboom"))

        result = await executor.execute_plan(
            plan={"action_type": "EXPLORE", "delegate_to": ["scene_builder"]},
            player_action="explore the forum",
            completed_events=[],
        )

        narrator.execute.assert_awaited_once()
        dramaturge.execute.assert_awaited_once()
        assert result == "Raw narration."
