"""Unit tests for the deterministic tactical-goal generator."""

from __future__ import annotations

import allure

from cast._npc_tactical_goal import (
    TACTICAL_TTL,
    assign_defend_goals_from_aggression,
    has_active_tactical_goal,
    promote_life_goals_on_sight,
    tick_tactical_ttl,
)
from models.goal import Goal, GoalKind, GoalScope, GoalStatus
from tests._aftermath_helpers import make_actor_target_state


@allure.epic("NPC Interaction")
@allure.feature("NPC autonomous goals")
class TestAssignDefendGoals:
    """``assign_defend_goals_from_aggression`` deterministically reacts to player attacks."""

    @allure.story("DEFEND assignment")
    @allure.title("Player attack stamps a tactical DEFEND on the targeted NPC")
    def test_defend_goal_set_on_target(self) -> None:
        state, actor, _target, _location = make_actor_target_state()
        state.player.uuid = "player-1"

        assign_defend_goals_from_aggression(state, [actor.uuid], "punches Brutus")

        assert actor.tactical_goal is not None
        assert actor.tactical_goal.scope is GoalScope.TACTICAL
        assert actor.tactical_goal.kind is GoalKind.DEFEND
        assert actor.tactical_goal.target_uuid == "player-1"
        assert actor.tactical_goal.created_on_turn == state.turn_count

    @allure.story("DEFEND assignment")
    @allure.title("Existing ACTIVE tactical goal blocks DEFEND override")
    def test_existing_tactical_goal_wins(self) -> None:
        state, actor, _target, _location = make_actor_target_state()
        actor.tactical_goal = Goal(
            scope=GoalScope.TACTICAL,
            kind=GoalKind.KILL,
            description="finish the vendetta",
            target_uuid="other",
        )

        assign_defend_goals_from_aggression(state, [actor.uuid], "shoves")

        assert actor.tactical_goal.kind is GoalKind.KILL  # unchanged

    @allure.story("DEFEND assignment")
    @allure.title("Unknown UUIDs are silently skipped")
    def test_unknown_uuid_is_noop(self) -> None:
        state, _actor, _target, _location = make_actor_target_state()
        assign_defend_goals_from_aggression(state, ["ghost-uuid"], "punches air")
        assert all(npc.tactical_goal is None for npc in state.npcs.values())


@allure.epic("NPC Interaction")
@allure.feature("NPC autonomous goals")
class TestLifeOnSightPromotion:
    """``promote_life_goals_on_sight`` mirrors a life-tier KILL into the tactical slot."""

    @allure.story("Promotion")
    @allure.title("Life-tier KILL promotes to tactical KILL when target is in scene")
    def test_kill_promoted_when_target_present(self) -> None:
        state, actor, target, _location = make_actor_target_state()
        actor.life_goal = Goal(
            kind=GoalKind.KILL,
            description="Avenge brother",
            target_uuid=target.uuid,
        )

        promote_life_goals_on_sight(state)

        assert actor.tactical_goal is not None
        assert actor.tactical_goal.scope is GoalScope.TACTICAL
        assert actor.tactical_goal.kind is GoalKind.KILL
        assert actor.tactical_goal.target_uuid == target.uuid

    @allure.story("Promotion")
    @allure.title("Promotion is a no-op when target is not in the scene")
    def test_no_promotion_without_target(self) -> None:
        state, actor, _target, _location = make_actor_target_state()
        actor.life_goal = Goal(
            kind=GoalKind.KILL,
            description="hunt someone",
            target_uuid="missing-uuid",
        )

        promote_life_goals_on_sight(state)

        assert actor.tactical_goal is None

    @allure.story("Promotion")
    @allure.title("Already-active tactical goal is not overwritten by promotion")
    def test_promotion_preserves_existing_tactical(self) -> None:
        state, actor, target, _location = make_actor_target_state()
        actor.life_goal = Goal(
            kind=GoalKind.KILL,
            description="vendetta",
            target_uuid=target.uuid,
        )
        actor.tactical_goal = Goal(
            scope=GoalScope.TACTICAL,
            kind=GoalKind.DEFEND,
            description="hold ground",
        )

        promote_life_goals_on_sight(state)

        assert actor.tactical_goal.kind is GoalKind.DEFEND  # unchanged

    @allure.story("Promotion")
    @allure.title("Non-promotable kinds (PROTECT, FLEE) are left alone")
    def test_non_promotable_kinds_skipped(self) -> None:
        state, actor, target, _location = make_actor_target_state()
        actor.life_goal = Goal(
            kind=GoalKind.PROTECT,
            description="guard family",
            target_uuid=target.uuid,
        )

        promote_life_goals_on_sight(state)

        assert actor.tactical_goal is None


@allure.epic("NPC Interaction")
@allure.feature("NPC autonomous goals")
class TestTacticalTTL:
    """``tick_tactical_ttl`` retires stale tactical goals."""

    @allure.story("TTL")
    @allure.title("Tactical goal expires after TACTICAL_TTL turns elapse")
    def test_ttl_expiry_abandons_goal(self) -> None:
        state, actor, _target, _location = make_actor_target_state()
        state.turn_count = 5
        actor.tactical_goal = Goal(
            scope=GoalScope.TACTICAL,
            kind=GoalKind.DEFEND,
            description="reaction",
            created_on_turn=5 - TACTICAL_TTL,
        )

        tick_tactical_ttl(state)

        assert actor.tactical_goal.status is GoalStatus.ABANDONED
        assert any("TTL expired" in note for note in actor.tactical_goal.progress_notes)

    @allure.story("TTL")
    @allure.title("Tactical goal whose target is dead flips to ABANDONED")
    def test_dead_target_abandons_goal(self) -> None:
        state, actor, target, _location = make_actor_target_state()
        target.physical_status = "dead"
        actor.tactical_goal = Goal(
            scope=GoalScope.TACTICAL,
            kind=GoalKind.KILL,
            description="finish him",
            target_uuid=target.uuid,
            created_on_turn=state.turn_count,
        )

        tick_tactical_ttl(state)

        assert actor.tactical_goal.status is GoalStatus.ABANDONED

    @allure.story("TTL")
    @allure.title("Fresh tactical goal within TTL is preserved")
    def test_fresh_tactical_goal_preserved(self) -> None:
        state, actor, _target, _location = make_actor_target_state()
        state.turn_count = 1
        actor.tactical_goal = Goal(
            scope=GoalScope.TACTICAL,
            kind=GoalKind.DEFEND,
            description="reaction",
            created_on_turn=1,
        )

        tick_tactical_ttl(state)

        assert actor.tactical_goal.status is GoalStatus.ACTIVE


@allure.epic("NPC Interaction")
@allure.feature("NPC autonomous goals")
class TestActiveTacticalQuery:
    """``has_active_tactical_goal`` powers NPCTicker's eviction skip."""

    @allure.story("Active query")
    @allure.title("Active tactical goal is reported as active; life-only NPC is not")
    def test_active_tactical_signal(self) -> None:
        _state, actor, _target, _location = make_actor_target_state()
        assert has_active_tactical_goal(actor) is False

        actor.life_goal = Goal(kind=GoalKind.KILL, description="x", target_uuid="t")
        assert has_active_tactical_goal(actor) is False  # life-only doesn't count

        actor.tactical_goal = Goal(
            scope=GoalScope.TACTICAL,
            kind=GoalKind.DEFEND,
            description="hold",
        )
        assert has_active_tactical_goal(actor) is True

        actor.tactical_goal.status = GoalStatus.ABANDONED
        assert has_active_tactical_goal(actor) is False
