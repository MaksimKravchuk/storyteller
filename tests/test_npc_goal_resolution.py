"""Unit tests for NPC autonomous-action aftermath: goal progress, memory, completion."""

from __future__ import annotations

import allure
import pytest

from cast._npc_social_goal import maybe_complete_social_goal
from cast.dice import ContestOutcome, ContestRoll, ContestType, NPCAction
from cast.npc_goal_resolution import (
    ActionAftermath,
    maybe_complete_kill_goal,
    resolve_actions_aftermath,
    update_goal_progress,
)
from models.goal import Goal, GoalKind, GoalStatus
from models.npc_card import NPCCard
from models.relationship import Relationship, RelationshipKind
from tests._aftermath_helpers import (
    RecordingMemoryManager,
    make_actor_target_state,
    seed_kill_thread,
)
from tests._uuid_helpers import make_uuid


def _combat_roll(outcome: ContestOutcome) -> ContestRoll:
    return ContestRoll(
        contest_type=ContestType.COMBAT,
        outcome=outcome,
        actor_roll=10,
        target_roll=5,
        actor_bonus=0,
        target_bonus=0,
    )


@allure.epic("NPC Interaction")
@allure.feature("NPC autonomous goals")
class TestGoalProgress:
    """``update_goal_progress`` and ``maybe_complete_kill_goal`` advance NPC state."""

    @allure.story("Goal progression")
    @allure.title("update_goal_progress bumps the counter and records the action")
    def test_update_goal_progress_records(self) -> None:
        actor = NPCCard(
            name="Brutus",
            occupation="legionary",
            life_goal=Goal(kind=GoalKind.KILL, description="x", target_uuid=make_uuid("t")),
        )
        update_goal_progress(actor, "STEALTH", "moved to the shadows")
        assert actor.life_goal is not None
        assert actor.life_goal.turns_pursued == 1
        assert actor.life_goal.last_attempted_action == "STEALTH"
        assert "STEALTH: moved to the shadows" in actor.life_goal.progress_notes

    @allure.story("Goal progression")
    @allure.title("Goal-less or completed NPC sees update_goal_progress as a no-op")
    def test_update_goal_progress_skips_inactive(self) -> None:
        actor = NPCCard(
            name="Brutus",
            occupation="legionary",
            life_goal=Goal(
                kind=GoalKind.KILL,
                description="x",
                target_uuid=make_uuid("t"),
                status=GoalStatus.COMPLETED,
            ),
        )
        update_goal_progress(actor, "ATTACK", "stabbed")
        assert actor.life_goal is not None
        assert actor.life_goal.turns_pursued == 0

    @allure.story("Goal completion")
    @allure.title("KILL goal flips to COMPLETED and matching thread to resolved when target dies")
    def test_kill_goal_completes_when_target_dies(self) -> None:
        state, actor, target, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.KILL, description="x", target_uuid=target.uuid)
        seed_kill_thread(state, actor, target)
        target.physical_status = "dead"

        maybe_complete_kill_goal(actor, target, state)

        assert actor.life_goal.status is GoalStatus.COMPLETED
        assert state.world_state.threads[0].status == "resolved"

    @allure.story("Goal completion")
    @allure.title("Live target leaves KILL goal active and matching thread open")
    def test_kill_goal_stays_active_when_target_alive(self) -> None:
        state, actor, target, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.KILL, description="x", target_uuid=target.uuid)
        seed_kill_thread(state, actor, target)

        maybe_complete_kill_goal(actor, target, state)

        assert actor.life_goal.status is GoalStatus.ACTIVE
        assert state.world_state.threads[0].status == "open"

    @allure.story("Goal completion")
    @allure.title("BEFRIEND goal completes when relationship reaches friend threshold")
    def test_befriend_goal_completes_at_friend_threshold(self) -> None:
        state, actor, target, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.BEFRIEND, description="x", target_uuid=target.uuid)
        actor.relationships = [
            Relationship(target_uuid=str(target.uuid), kind=RelationshipKind.FRIEND, intensity=2),
        ]

        maybe_complete_social_goal(actor, state)

        assert actor.life_goal.status is GoalStatus.COMPLETED
        assert any("friend threshold" in note for note in actor.life_goal.progress_notes)

    @allure.story("Goal completion")
    @allure.title("BEFRIEND goal stays active below the friend threshold")
    def test_befriend_goal_stays_active_below_friend_threshold(self) -> None:
        state, actor, target, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.BEFRIEND, description="x", target_uuid=target.uuid)
        actor.relationships = [
            Relationship(target_uuid=str(target.uuid), kind=RelationshipKind.FRIEND, intensity=1),
        ]

        maybe_complete_social_goal(actor, state)

        assert actor.life_goal.status is GoalStatus.ACTIVE
        assert actor.life_goal.progress_notes == []


@allure.epic("Memory & Persistence")
@allure.feature("Autonomous combat memory")
class TestResolveActionsAftermath:
    """End-to-end aftermath: outcome → memory → goal → thread."""

    @pytest.mark.asyncio
    @allure.story("Lethal aftermath")
    @allure.title("Lethal ATTACK kills target, persists memory, completes goal, closes thread")
    async def test_lethal_attack_full_pipeline(self) -> None:
        state, actor, target, location = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.KILL, description="x", target_uuid=target.uuid)
        seed_kill_thread(state, actor, target)
        memory = RecordingMemoryManager()

        await resolve_actions_aftermath(
            [
                NPCAction(
                    npc_name="Brutus",
                    npc_uuid=actor.uuid,
                    action_type="ATTACK",
                    action_description="stabs Marcus",
                    target=target.name,
                    contest_roll=_combat_roll(ContestOutcome.ACTOR_DOMINATES),
                ),
            ],
            state,
            memory,
        )

        assert target.physical_status == "dead"
        assert actor.life_goal.status is GoalStatus.COMPLETED
        assert state.world_state.threads[0].status == "resolved"
        assert len(memory.calls) == 1
        recorded = memory.calls[0]
        assert "Brutus" in recorded["event_description"]
        assert "Marcus" in recorded["event_description"]
        assert "attacked" in recorded["event_description"]
        assert "killed" in recorded["event_description"]
        assert "lethal" in recorded["event_description"]
        assert recorded["location_id"] == location.uuid
        assert set(recorded["witness_ids"]) == {actor.uuid, target.uuid}

    @pytest.mark.asyncio
    @allure.story("Non-lethal aftermath")
    @allure.title("Non-lethal ATTACK wounds target and the wound shape reaches the persisted memory")
    async def test_non_lethal_attack_persists_wounded_resolution(self) -> None:
        state, actor, target, _ = make_actor_target_state()
        memory = RecordingMemoryManager()

        await resolve_actions_aftermath(
            [
                NPCAction(
                    npc_name="Brutus",
                    npc_uuid=actor.uuid,
                    action_type="ATTACK",
                    action_description="slashes at Marcus",
                    target=target.name,
                    contest_roll=_combat_roll(ContestOutcome.ACTOR_SUCCEEDS),
                ),
            ],
            state,
            memory,
        )

        assert target.physical_status == "wounded"
        assert len(memory.calls) == 1
        recorded = memory.calls[0]["event_description"]
        assert "wounded" in recorded
        assert "non-lethal" in recorded
        assert "killed" not in recorded

    @pytest.mark.asyncio
    @allure.story("Intimidation aftermath")
    @allure.title("Successful INTIMIDATE cows the target and the submission shape reaches the persisted memory")
    async def test_intimidation_persists_submission_resolution(self) -> None:
        state, actor, target, _ = make_actor_target_state()
        memory = RecordingMemoryManager()

        intimidation_roll = ContestRoll(
            contest_type=ContestType.INTIMIDATION,
            outcome=ContestOutcome.ACTOR_DOMINATES,
            actor_roll=18,
            target_roll=2,
            actor_bonus=0,
            target_bonus=0,
        )

        await resolve_actions_aftermath(
            [
                NPCAction(
                    npc_name="Brutus",
                    npc_uuid=actor.uuid,
                    action_type="INTIMIDATE",
                    action_description="looms over Marcus",
                    target=target.name,
                    contest_roll=intimidation_roll,
                ),
            ],
            state,
            memory,
        )

        assert target.current_mood == "frightened"
        assert len(memory.calls) == 1
        recorded = memory.calls[0]["event_description"]
        assert "intimidated" in recorded
        assert "frightened" in recorded
        assert "killed" not in recorded
        assert "wounded" not in recorded

    @pytest.mark.asyncio
    @allure.story("Stealth aftermath")
    @allure.title("STEALTH does not wound the target but still records goal progress")
    async def test_stealth_records_progress_only(self) -> None:
        state, actor, target, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.KILL, description="x", target_uuid=target.uuid)
        memory = RecordingMemoryManager()

        stealth_roll = ContestRoll(
            contest_type=ContestType.STEALTH,
            outcome=ContestOutcome.ACTOR_SUCCEEDS,
            actor_roll=10,
            target_roll=5,
            actor_bonus=0,
            target_bonus=0,
        )

        await resolve_actions_aftermath(
            [
                NPCAction(
                    npc_name="Brutus",
                    npc_uuid=actor.uuid,
                    action_type="STEALTH",
                    action_description="drifts in shadow",
                    target=target.name,
                    contest_roll=stealth_roll,
                ),
            ],
            state,
            memory,
        )

        assert target.physical_status == "healthy"
        assert actor.life_goal.status is GoalStatus.ACTIVE
        assert actor.life_goal.last_attempted_action == "STEALTH"
        assert memory.calls == []

    @pytest.mark.asyncio
    @allure.story("Social aftermath")
    @allure.title("Warm TALK aftermath completes a BEFRIEND goal without combat memory")
    async def test_talk_completes_befriend_goal_without_combat_memory(self) -> None:
        state, actor, target, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.BEFRIEND, description="x", target_uuid=target.uuid)
        actor.relationships = [
            Relationship(target_uuid=str(target.uuid), kind=RelationshipKind.FRIEND, intensity=2),
        ]
        memory = RecordingMemoryManager()

        await resolve_actions_aftermath(
            [
                NPCAction(
                    npc_name="Brutus",
                    npc_uuid=actor.uuid,
                    action_type="TALK",
                    action_description="shares a warm conversation",
                    target=target.name,
                    contest_roll=None,
                ),
            ],
            state,
            memory,
        )

        assert actor.life_goal.status is GoalStatus.COMPLETED
        assert actor.life_goal.last_attempted_action == "TALK"
        assert memory.calls == []

    @pytest.mark.asyncio
    @allure.story("Social aftermath")
    @allure.title("Satisfied BEFRIEND goal completes even when this turn's action names no target")
    async def test_untargeted_action_completes_satisfied_befriend_goal(self) -> None:
        state, actor, target, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.BEFRIEND, description="x", target_uuid=target.uuid)
        actor.relationships = [
            Relationship(target_uuid=str(target.uuid), kind=RelationshipKind.ALLY, intensity=3),
        ]

        await resolve_actions_aftermath(
            [
                NPCAction(
                    npc_name="Brutus",
                    npc_uuid=actor.uuid,
                    action_type="IDLE",
                    action_description="nurses his cup",
                    target=None,
                    contest_roll=None,
                ),
            ],
            state,
            RecordingMemoryManager(),
        )

        assert actor.life_goal.status is GoalStatus.COMPLETED
        assert any(target.name in note for note in actor.life_goal.progress_notes)

    @pytest.mark.asyncio
    @allure.story("Social aftermath")
    @allure.title("BEFRIEND goal never completes toward a dead target")
    async def test_befriend_goal_stays_active_when_target_is_dead(self) -> None:
        state, actor, target, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.BEFRIEND, description="x", target_uuid=target.uuid)
        actor.relationships = [
            Relationship(target_uuid=str(target.uuid), kind=RelationshipKind.FRIEND, intensity=2),
        ]
        target.physical_status = "dead"

        await resolve_actions_aftermath(
            [
                NPCAction(
                    npc_name="Brutus",
                    npc_uuid=actor.uuid,
                    action_type="TALK",
                    action_description="mourns over the body",
                    target=target.name,
                    contest_roll=None,
                ),
            ],
            state,
            RecordingMemoryManager(),
        )

        assert actor.life_goal.status is GoalStatus.ACTIVE

    @pytest.mark.asyncio
    @allure.story("Aftermath wiring")
    @allure.title("ActionAftermath bundles all fields and an empty-target run still ticks goal progress")
    async def test_aftermath_dataclass_fields_round_trip(self) -> None:
        state, actor, _, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.KILL, description="x", target_uuid=make_uuid("missing"))
        memory = RecordingMemoryManager()

        await resolve_actions_aftermath(
            [
                NPCAction(
                    npc_name="Brutus",
                    npc_uuid=actor.uuid,
                    action_type="IDLE",
                    action_description="watches the door",
                    target=None,
                    contest_roll=None,
                ),
            ],
            state,
            memory,
        )

        assert actor.life_goal.turns_pursued == 1
        assert actor.life_goal.last_attempted_action == "IDLE"
        assert memory.calls == []

        bundle = ActionAftermath(
            actor=actor,
            action_type="IDLE",
            action_description="x",
            target_name=None,
            contest_roll=None,
        )
        assert bundle.action_type == "IDLE"
