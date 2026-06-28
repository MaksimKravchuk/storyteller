"""Unit tests for the gated standing-goal Actor prompt section."""

from __future__ import annotations

import allure

from cast.actor_config import goal_outcome_var, goal_prompt_vars
from models.goal import Goal, GoalKind, GoalStatus, OffSceneOutcome, OffSceneOutcomeKind
from models.npc_card import NPCCard
from tests._uuid_helpers import make_uuid


def _kill_marcus(npc_name: str = "Brutus") -> NPCCard:
    return NPCCard(
        name=npc_name,
        occupation="former legionary",
        life_goal=Goal(
            kind=GoalKind.KILL,
            description="Avenge brother by killing Marcus",
            target_uuid=make_uuid("npc-marcus"),
        ),
    )


@allure.epic("NPC Interaction")
@allure.feature("NPC autonomous goals")
class TestGoalPromptVars:
    """``goal_prompt_vars`` gates the optional Actor goal section by NPC state."""

    @allure.story("Section gating")
    @allure.title("Returns None when the NPC has no goal at all")
    def test_no_goal_returns_none(self) -> None:
        npc = NPCCard(name="Anon", occupation="merchant")
        assert goal_prompt_vars(npc, "Marcus", "English") is None

    @allure.story("Section gating")
    @allure.title("Returns None when the goal exists but is no longer ACTIVE")
    def test_completed_goal_returns_none(self) -> None:
        npc = _kill_marcus()
        assert npc.life_goal is not None
        npc.life_goal.status = GoalStatus.COMPLETED
        assert goal_prompt_vars(npc, "Marcus", "English") is None

    @allure.story("Active goal rendering")
    @allure.title("Active goal returns the full var bundle the prompt section expects")
    def test_active_goal_returns_full_vars(self) -> None:
        npc = _kill_marcus()
        assert npc.life_goal is not None
        npc.life_goal.last_attempted_action = "STEALTH"
        npc.life_goal.record_progress("approached the table from the shadows")

        rendered = goal_prompt_vars(npc, "Marcus", "English")

        assert rendered is not None
        assert rendered["goal_kind"] == "kill"
        assert rendered["goal_target"] == "Marcus"
        assert rendered["goal_description"] == "Avenge brother by killing Marcus"
        assert rendered["goal_last_action"] == "STEALTH"
        assert "approached the table" in rendered["goal_progress_notes"]
        # A KILL goal is hostile — the coaching var carries the combat escalation.
        assert "commit to ATTACK now" in rendered["goal_coaching"]

    @allure.story("Active goal rendering")
    @allure.title("Empty progress and unset last_action render fallbacks instead of the empty string")
    def test_fallbacks_when_no_history(self) -> None:
        npc = _kill_marcus()
        rendered = goal_prompt_vars(npc, None, "English")

        assert rendered is not None
        assert rendered["goal_target"] == "(unspecified)"
        assert rendered["goal_last_action"] == "(none yet)"
        assert "no notes yet" in rendered["goal_progress_notes"]

    @allure.story("Off-scene outcome")
    @allure.title("goal_outcome_var is None when the life goal has no recorded outcome")
    def test_no_outcome_var_when_unset(self) -> None:
        npc = _kill_marcus()
        assert goal_outcome_var(npc, "English") is None

    @allure.story("Off-scene outcome")
    @allure.title("goal_outcome_var renders the structured outcome as a localized sentence")
    def test_outcome_var_localized(self) -> None:
        npc = NPCCard(
            name="Cassia",
            occupation="thief",
            life_goal=Goal(kind=GoalKind.ACQUIRE, description="the senator's ledger"),
        )
        assert npc.life_goal is not None
        npc.life_goal.last_outcome = OffSceneOutcome(
            kind=OffSceneOutcomeKind.ACQUIRE_SECURED, detail="the senator's ledger"
        )

        assert goal_outcome_var(npc, "English") == "secured the senator's ledger"
        assert goal_outcome_var(npc, "Russian") == "добыл(а) желаемое: the senator's ledger"

    @allure.story("Off-scene outcome")
    @allure.title("goal_outcome_var surfaces a completed life goal's outcome (consumer-seam gap)")
    def test_outcome_var_survives_goal_completion(self) -> None:
        npc = NPCCard(
            name="Cassia",
            occupation="thief",
            life_goal=Goal(kind=GoalKind.ACQUIRE, description="a relic"),
        )
        assert npc.life_goal is not None
        npc.life_goal.status = GoalStatus.COMPLETED
        npc.life_goal.last_outcome = OffSceneOutcome(kind=OffSceneOutcomeKind.ACQUIRE_SECURED, detail="a relic")

        # select_active_goal would drop a COMPLETED goal, but the outcome must still surface.
        assert goal_prompt_vars(npc, None, "English") is None
        assert goal_outcome_var(npc, "English") == "secured a relic"
