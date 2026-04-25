"""Unit tests for the Goal model and its NPCCard wiring."""

from __future__ import annotations

import allure

from models.goal import Goal, GoalKind, GoalScope, GoalStatus
from models.npc_card import NPCCard


def _kill_marcus_goal(last_attempted_action: str | None = None) -> Goal:
    """Build a baseline life-tier KILL goal targeting Marcus, with optional last-action."""
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
    @allure.title("NPCCard.life_goal and tactical_goal both default to None")
    def test_npc_card_default_goal_is_none(self) -> None:
        npc = NPCCard(name="Anon", occupation="merchant")
        assert npc.life_goal is None
        assert npc.tactical_goal is None

    @allure.story("Two-tier scope")
    @allure.title("Goal.scope defaults to LIFE; tactical scope round-trips through JSON")
    def test_goal_scope_defaults_to_life(self) -> None:
        life_goal = _kill_marcus_goal()
        tactical = Goal(scope=GoalScope.TACTICAL, kind=GoalKind.DEFEND, description="hit back")

        assert life_goal.scope is GoalScope.LIFE
        assert tactical.scope is GoalScope.TACTICAL
        revived = Goal.model_validate_json(tactical.model_dump_json())
        assert revived.scope is GoalScope.TACTICAL
        assert revived.kind is GoalKind.DEFEND

    @allure.story("Persistence")
    @allure.title("Goal preserves every field through pydantic JSON dump and reparse")
    def test_goal_round_trips_through_json(self) -> None:
        goal = _kill_marcus_goal(last_attempted_action="STEALTH")
        goal.record_progress("approached the table")

        revived = Goal.model_validate_json(goal.model_dump_json())

        assert revived.scope is GoalScope.LIFE
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
    @allure.title("NPCCard exposes the seeded Goal on its life_goal field")
    def test_npc_card_carries_a_goal(self) -> None:
        npc = NPCCard(
            name="Brutus",
            occupation="former legionary",
            life_goal=_kill_marcus_goal(),
        )

        assert npc.life_goal is not None
        assert npc.life_goal.kind is GoalKind.KILL
        assert npc.life_goal.target_uuid == "npc-marcus"
