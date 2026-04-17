"""End-of-turn ``player_event_log`` writes in ``PlanExecutor``.

Exercises :meth:`cast.director_execution.PlanExecutor._append_player_event_log`
directly: the Character sidebar depends on the log being populated from
the same ``raw_outputs`` fields the Narrator consumes, and on the 30-entry
cap so long play sessions don't balloon the payload.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import allure

from cast import director_execution
from cast.schemas import turn_outputs
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.setting import Setting


pytestmark = [
    allure.epic("Memory & Persistence"),
    allure.feature("GameState model"),
]


def _build_plan_executor() -> tuple[director_execution.PlanExecutor, GameState]:
    setting = Setting(name="Rome", time_period="1 AD", region="Italy", summary="")
    gs = GameState(setting=setting, knowledge_graph=KnowledgeGraph())
    executor = director_execution.PlanExecutor(
        gs,
        agents=MagicMock(),
        cast=MagicMock(),
        register_npc_fn=lambda _card: None,
    )
    return executor, gs


@allure.story("Player event log")
@allure.title("Appends new_npcs, completed_events, and object_interactions lines verbatim")
def test_event_log_collects_narrator_strings() -> None:
    executor, gs = _build_plan_executor()
    raw = turn_outputs.TurnOutputs(
        new_npcs=["Marcus (legionary)"],
        completed_events=["The temple bell tolls noon."],
        object_interactions=["The clay amphora shatters."],
    )

    executor._append_player_event_log(raw)

    assert gs.player.player_event_log == [
        "Marcus (legionary)",
        "The temple bell tolls noon.",
        "The clay amphora shatters.",
    ]


@allure.story("Player event log")
@allure.title("Leaves the log untouched on a turn that produced none of the tracked outputs")
def test_event_log_noop_when_nothing_to_log() -> None:
    executor, gs = _build_plan_executor()
    gs.player.player_event_log = ["earlier entry"]

    executor._append_player_event_log(turn_outputs.TurnOutputs())

    assert gs.player.player_event_log == ["earlier entry"]


@allure.story("Player event log")
@allure.title("Caps the log at 30 entries, trimming the oldest off the front")
def test_event_log_trims_to_cap() -> None:
    executor, gs = _build_plan_executor()
    gs.player.player_event_log = [f"old-{idx}" for idx in range(28)]
    raw = turn_outputs.TurnOutputs(
        new_npcs=["new-a", "new-b", "new-c", "new-d"],
    )

    executor._append_player_event_log(raw)

    assert len(gs.player.player_event_log) == 30
    assert gs.player.player_event_log[0] == "old-2"
    assert gs.player.player_event_log[-1] == "new-d"
