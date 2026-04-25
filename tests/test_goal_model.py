"""Unit tests for the Goal model and its NPCCard wiring."""

from __future__ import annotations

import allure

from models.goal import Goal, GoalKind, GoalStatus
from models.npc_card import NPCCard


def _kill_marcus_goal(last_attempted_action: str | None = None) -> Goal:
    """Build a baseline KILL goal targeting Marcus, with an optional last-action."""
    return Goal(
        kind=GoalKind.KILL,
        description="Avenge brother by killing Marcus",
        target_uuid="npc-marcus",
        last_attempted_action=last_attempted_action,
    )


@allure.epic("NPC Interaction")
@allure.feature("NPC autonomous goals")
class TestGoalModel:
    """Persistent NPC intentions carry across turns and round-trip through JSON."""

    @allure.story("NPCCard default state")
    @allure.title("NPCCard.current_goal defaults to None for legacy NPCs")
    def test_npc_card_default_goal_is_none(self) -> None:
        npc = NPCCard(name="Anon", occupation="merchant")
        assert npc.current_goal is None

    @allure.story("Persistence")
    @allure.title("Goal preserves every field through pydantic JSON dump and reparse")
    def test_goal_round_trips_through_json(self) -> None:
        goal = _kill_marcus_goal(last_attempted_action="STEALTH")
        goal.record_progress("approached the table")

        revived = Goal.model_validate_json(goal.model_dump_json())

        assert revived.kind is GoalKind.KILL
        assert revived.description == "Avenge brother by killing Marcus"
        assert revived.target_uuid == "npc-marcus"
        assert revived.status is GoalStatus.ACTIVE
        assert revived.last_attempted_action == "STEALTH"
        assert revived.progress_notes == ["approached the table"]

    @allure.story("Bounded progress notes")
    @allure.title("record_progress drops the oldest entry once the budget is exceeded")
    def test_record_progress_caps_notes(self) -> None:
        goal = _kill_marcus_goal()
        for index in range(20):
            goal.record_progress("step {0}".format(index))

        assert len(goal.progress_notes) == 6
        assert goal.progress_notes[0] == "step 14"
        assert goal.progress_notes[-1] == "step 19"

    @allure.story("NPCCard goal carrier")
    @allure.title("NPCCard exposes the seeded Goal on its current_goal field")
    def test_npc_card_carries_a_goal(self) -> None:
        npc = NPCCard(
            name="Brutus",
            occupation="former legionary",
            current_goal=_kill_marcus_goal(),
        )

        assert npc.current_goal is not None
        assert npc.current_goal.kind is GoalKind.KILL
        assert npc.current_goal.target_uuid == "npc-marcus"
