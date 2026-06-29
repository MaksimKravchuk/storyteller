"""Unit tests for the off-scene NPC goal ticker."""

from __future__ import annotations

from unittest.mock import patch

import allure
import pytest

from cast.dice import ContestOutcome, ContestRoll, ContestType
from cast.npc_background_tick import NPCBackgroundTicker, _is_eligible
from models.goal import Goal, GoalKind, GoalStatus, OffSceneOutcome, OffSceneOutcomeKind
from models.location import Location
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from tests._uuid_helpers import make_uuid
from tests._aftermath_helpers import RecordingMemoryManager, make_actor_target_state, seed_kill_thread


def _strand_actor_alone(state, actor: NPCCard) -> Location:
    """Relocate the actor to a fresh off-scene location with no target nearby."""
    far_off = Location(name="Docks", description="", location_type="building")
    state.locations[far_off.uuid] = far_off
    actor.location_id = far_off.uuid
    far_off.add_npc(actor.uuid)
    if state.current_scene is not None:
        state.current_scene = Scene(
            location_id=state.current_scene.location_id,
            description="",
            npcs_present=[SceneNPC(role="bystander", uuid=make_uuid("player-only"))],
        )
    return far_off


def _move_actor_offscene(state, actor: NPCCard, target: NPCCard) -> Location:
    """Relocate the actor + target to a fresh off-scene location, leaving the scene empty."""
    other = Location(name="Backroom", description="", location_type="building")
    state.locations[other.uuid] = other
    actor.location_id = other.uuid
    target.location_id = other.uuid
    other.add_npc(actor.uuid)
    other.add_npc(target.uuid)
    if state.current_scene is not None:
        state.current_scene = Scene(
            location_id=state.current_scene.location_id,
            description="",
            npcs_present=[SceneNPC(role="bystander", uuid=make_uuid("player-only"))],
        )
    return other


@allure.epic("NPC Interaction")
@allure.feature("Off-scene goal pursuit")
class TestNPCBackgroundTicker:
    """``NPCBackgroundTicker`` advances goals when the player isn't watching."""

    @pytest.mark.asyncio
    @allure.story("Threshold gating")
    @allure.title("Tick is a no-op when the clock barely moved")
    async def test_short_advance_no_op(self) -> None:
        state, actor, target, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.KILL, description="x", target_uuid=target.uuid)
        memory = RecordingMemoryManager()

        ticker = NPCBackgroundTicker(state, memory)
        await ticker.tick(hours_advanced=0.5)

        assert actor.life_goal.turns_pursued == 0
        assert memory.calls == []

    @pytest.mark.asyncio
    @allure.story("Eligibility")
    @allure.title("Tick skips a dead goal-holder so corpses don't keep stalking off-scene")
    async def test_dead_actor_skipped(self) -> None:
        state, actor, target, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.KILL, description="x", target_uuid=target.uuid)
        _move_actor_offscene(state, actor, target)
        actor.physical_status = "dead"
        memory = RecordingMemoryManager()

        ticker = NPCBackgroundTicker(state, memory)
        await ticker.tick(hours_advanced=8.0)

        assert target.physical_status == "healthy"
        assert actor.life_goal.turns_pursued == 0
        assert memory.calls == []

    @pytest.mark.asyncio
    @allure.story("Eligibility")
    @allure.title("Tick skips on-scene NPCs — they get their normal NPC turn instead")
    async def test_on_scene_npcs_skipped(self) -> None:
        state, actor, target, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.KILL, description="x", target_uuid=target.uuid)
        memory = RecordingMemoryManager()

        ticker = NPCBackgroundTicker(state, memory)
        await ticker.tick(hours_advanced=8.0)

        assert actor.life_goal.turns_pursued == 0
        assert memory.calls == []

    @pytest.mark.asyncio
    @allure.story("Co-located target")
    @allure.title("Off-scene actor with co-located target rolls a contest and persists the outcome")
    async def test_co_located_off_scene_pair_resolves(self) -> None:
        state, actor, target, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.KILL, description="x", target_uuid=target.uuid)
        seed_kill_thread(state, actor, target)
        backroom = _move_actor_offscene(state, actor, target)
        memory = RecordingMemoryManager()

        forced_roll = ContestRoll(
            contest_type=ContestType.COMBAT,
            outcome=ContestOutcome.ACTOR_DOMINATES,
            actor_roll=20,
            target_roll=1,
            actor_bonus=0,
            target_bonus=0,
        )
        ticker = NPCBackgroundTicker(state, memory)
        with patch("cast.npc_background_tick.roll_contest", return_value=forced_roll):
            await ticker.tick(hours_advanced=8.0)

        assert target.physical_status == "dead"
        assert actor.life_goal.status is GoalStatus.COMPLETED
        assert state.world_state.threads[0].status == "resolved"
        assert len(memory.calls) == 1
        assert memory.calls[0]["location_id"] == backroom.uuid
        assert memory.calls[0]["salience"] == pytest.approx(0.85)  # salience_presets.COMBAT

    @pytest.mark.asyncio
    @allure.story("Lone actor")
    @allure.title("Off-scene actor without target nearby just records progress and ticks turns")
    async def test_no_target_nearby_records_progress(self) -> None:
        state, actor, target, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.KILL, description="x", target_uuid=target.uuid)
        _strand_actor_alone(state, actor)
        memory = RecordingMemoryManager()

        ticker = NPCBackgroundTicker(state, memory)
        await ticker.tick(hours_advanced=8.0)

        assert actor.life_goal.turns_pursued == 1
        assert any("offscreen wait" in note for note in actor.life_goal.progress_notes)
        assert actor.life_goal.last_outcome is None  # KILL never stamps last_outcome
        assert target.physical_status == "healthy"
        assert memory.calls == []


@allure.epic("NPC Interaction")
@allure.feature("Off-scene goal pursuit")
class TestOffSceneNonKillResolvers:
    """PURSUE / ACQUIRE / REST resolve deterministically off-scene (no LLM, no dice)."""

    @pytest.mark.parametrize("goal_kind", [GoalKind.PURSUE, GoalKind.ACQUIRE, GoalKind.REST])
    @allure.story("Eligibility")
    @allure.title("_is_eligible accepts every non-KILL goal kind with a deterministic resolver")
    def test_is_eligible_accepts_resolved_non_kill_goal_kinds(self, goal_kind: GoalKind) -> None:
        state, actor, _, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=goal_kind, description="resolved off-scene")
        _strand_actor_alone(state, actor)

        assert _is_eligible(actor, set()) is True

    @pytest.mark.asyncio
    @allure.story("PURSUE")
    @allure.title("PURSUE goal-holder co-located with quarry stamps a 'caught up' outcome")
    async def test_pursue_caught_up(self) -> None:
        state, actor, target, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.PURSUE, description="shadow Marcus", target_uuid=target.uuid)
        _move_actor_offscene(state, actor, target)
        memory = RecordingMemoryManager()

        ticker = NPCBackgroundTicker(state, memory)
        await ticker.tick(hours_advanced=8.0)

        assert actor.life_goal.turns_pursued == 1
        assert actor.life_goal.last_outcome == OffSceneOutcome(
            kind=OffSceneOutcomeKind.PURSUE_CAUGHT_UP, detail="Marcus"
        )
        assert target.physical_status == "healthy"  # PURSUE is non-lethal — no contest
        assert memory.calls == []

    @pytest.mark.asyncio
    @allure.story("PURSUE")
    @allure.title("PURSUE goal-holder with no quarry nearby stamps a 'still on the trail' outcome")
    async def test_pursue_still_tracking(self) -> None:
        state, actor, target, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.PURSUE, description="shadow Marcus", target_uuid=target.uuid)
        _strand_actor_alone(state, actor)
        memory = RecordingMemoryManager()

        ticker = NPCBackgroundTicker(state, memory)
        await ticker.tick(hours_advanced=8.0)

        assert actor.life_goal.turns_pursued == 1
        assert actor.life_goal.last_outcome == OffSceneOutcome(
            kind=OffSceneOutcomeKind.PURSUE_TRACKING, detail="Marcus"
        )

    @pytest.mark.asyncio
    @allure.story("ACQUIRE")
    @allure.title("ACQUIRE goal accrues headway before the securing threshold")
    async def test_acquire_makes_headway(self) -> None:
        state, actor, _, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.ACQUIRE, description="the senator's ledger")
        _strand_actor_alone(state, actor)
        memory = RecordingMemoryManager()

        ticker = NPCBackgroundTicker(state, memory)
        await ticker.tick(hours_advanced=8.0)

        assert actor.life_goal.status is GoalStatus.ACTIVE
        assert actor.life_goal.last_outcome == OffSceneOutcome(
            kind=OffSceneOutcomeKind.ACQUIRE_PROGRESS, detail="the senator's ledger"
        )

    @pytest.mark.asyncio
    @allure.story("ACQUIRE")
    @allure.title("ACQUIRE goal completes once it has accrued enough off-scene steps")
    async def test_acquire_secures_after_threshold(self) -> None:
        state, actor, _, _ = make_actor_target_state()
        actor.life_goal = Goal(
            kind=GoalKind.ACQUIRE,
            description="the senator's ledger",
            turns_pursued=2,
        )
        _strand_actor_alone(state, actor)
        memory = RecordingMemoryManager()

        ticker = NPCBackgroundTicker(state, memory)
        await ticker.tick(hours_advanced=8.0)

        assert actor.life_goal.status is GoalStatus.COMPLETED
        assert actor.life_goal.last_outcome == OffSceneOutcome(
            kind=OffSceneOutcomeKind.ACQUIRE_SECURED, detail="the senator's ledger"
        )

    @pytest.mark.asyncio
    @allure.story("REST")
    @allure.title("REST goal heals a recoverable status to healthy and completes")
    async def test_rest_heals_and_completes(self) -> None:
        state, actor, _, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.REST, description="recover from the brawl")
        actor.physical_status = "wounded"
        _strand_actor_alone(state, actor)
        memory = RecordingMemoryManager()

        ticker = NPCBackgroundTicker(state, memory)
        await ticker.tick(hours_advanced=8.0)

        assert actor.physical_status == "healthy"
        assert actor.life_goal.status is GoalStatus.COMPLETED
        assert actor.life_goal.last_outcome == OffSceneOutcome(kind=OffSceneOutcomeKind.REST_RECOVERED)

    @pytest.mark.asyncio
    @allure.story("REST")
    @allure.title("Healthy REST goal-holder just logs the lull without completing")
    async def test_rest_already_healthy_logs_lull(self) -> None:
        state, actor, _, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.REST, description="take it easy")
        _strand_actor_alone(state, actor)
        memory = RecordingMemoryManager()

        ticker = NPCBackgroundTicker(state, memory)
        await ticker.tick(hours_advanced=8.0)

        assert actor.physical_status == "healthy"
        assert actor.life_goal.status is GoalStatus.ACTIVE
        assert actor.life_goal.last_outcome == OffSceneOutcome(kind=OffSceneOutcomeKind.REST_AT_EASE)

    @pytest.mark.asyncio
    @allure.story("Eligibility")
    @allure.title("Eligibility is no longer KILL-only — a non-KILL goal-holder ticks off-scene")
    async def test_non_kill_goal_is_eligible(self) -> None:
        state, actor, _, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.ACQUIRE, description="coin")
        _strand_actor_alone(state, actor)

        ticker = NPCBackgroundTicker(state, RecordingMemoryManager())
        await ticker.tick(hours_advanced=8.0)

        assert actor.life_goal.turns_pursued == 1

    @pytest.mark.asyncio
    @allure.story("Cost")
    @allure.title("Background ticking does not route deterministic resolvers through an LLM client")
    async def test_non_kill_background_tick_makes_no_llm_calls(self) -> None:
        state, actor, target, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.PURSUE, description="shadow Marcus", target_uuid=target.uuid)
        target.life_goal = Goal(kind=GoalKind.ACQUIRE, description="the senator's ledger")
        _move_actor_offscene(state, actor, target)
        memory = RecordingMemoryManager()

        no_llm = AssertionError("background tick must not call an LLM")
        ticker = NPCBackgroundTicker(state, memory)
        with (
            patch("llm.factory.create_llm_client", side_effect=no_llm),
            patch("llm.openai_client.OpenAIClient.send_message", side_effect=no_llm),
            patch("llm.anthropic_client.AnthropicClient.send_message", side_effect=no_llm),
        ):
            await ticker.tick(hours_advanced=8.0)

        assert actor.life_goal.last_outcome == OffSceneOutcome(
            kind=OffSceneOutcomeKind.PURSUE_CAUGHT_UP, detail="Marcus"
        )
        assert target.life_goal.last_outcome == OffSceneOutcome(
            kind=OffSceneOutcomeKind.ACQUIRE_PROGRESS, detail="the senator's ledger"
        )
        assert memory.calls == []

    @pytest.mark.asyncio
    @allure.story("Eligibility")
    @allure.title("A goal kind without a resolver is still skipped off-scene")
    async def test_unresolved_goal_kind_skipped(self) -> None:
        state, actor, _, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.PROTECT, description="guard the gate")
        _strand_actor_alone(state, actor)

        ticker = NPCBackgroundTicker(state, RecordingMemoryManager())
        await ticker.tick(hours_advanced=8.0)

        assert actor.life_goal.turns_pursued == 0
        assert actor.life_goal.last_outcome is None

    @pytest.mark.asyncio
    @allure.story("PURSUE")
    @allure.title("PURSUE goal whose quarry was killed elsewhere abandons the chase")
    async def test_pursue_dead_quarry_abandons(self) -> None:
        state, actor, target, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.PURSUE, description="shadow Marcus", target_uuid=target.uuid)
        target.physical_status = "dead"
        _strand_actor_alone(state, actor)

        ticker = NPCBackgroundTicker(state, RecordingMemoryManager())
        await ticker.tick(hours_advanced=8.0)

        assert actor.life_goal.status is GoalStatus.ABANDONED
        assert actor.life_goal.last_outcome == OffSceneOutcome(
            kind=OffSceneOutcomeKind.PURSUE_TARGET_DEAD, detail="Marcus"
        )

    @pytest.mark.asyncio
    @allure.story("REST")
    @allure.title("REST heals a free-form injury status, not just exact-match statuses")
    async def test_rest_heals_free_form_status(self) -> None:
        state, actor, _, _ = make_actor_target_state()
        actor.life_goal = Goal(kind=GoalKind.REST, description="mend")
        actor.physical_status = "wounded left arm"
        _strand_actor_alone(state, actor)

        ticker = NPCBackgroundTicker(state, RecordingMemoryManager())
        await ticker.tick(hours_advanced=8.0)

        assert actor.physical_status == "healthy"
        assert actor.life_goal.status is GoalStatus.COMPLETED

    @pytest.mark.asyncio
    @allure.story("Eligibility")
    @allure.title("An actor killed earlier in the same tick does not run its own resolver")
    async def test_actor_killed_mid_tick_skips_resolver(self) -> None:
        # Brutus (KILL) and a co-located ACQUIRE holder are both off-scene
        # and eligible; Brutus's lethal contest kills the ACQUIRE holder
        # before its resolver runs, so the corpse must not "secure" anything.
        state, brutus, victim, _ = make_actor_target_state()
        brutus.life_goal = Goal(kind=GoalKind.KILL, description="kill Marcus", target_uuid=victim.uuid)
        victim.life_goal = Goal(kind=GoalKind.ACQUIRE, description="a fortune", turns_pursued=2)
        seed_kill_thread(state, brutus, victim)
        _move_actor_offscene(state, brutus, victim)

        forced_roll = ContestRoll(
            contest_type=ContestType.COMBAT,
            outcome=ContestOutcome.ACTOR_DOMINATES,
            actor_roll=20,
            target_roll=1,
            actor_bonus=0,
            target_bonus=0,
        )
        ticker = NPCBackgroundTicker(state, RecordingMemoryManager())
        with patch("cast.npc_background_tick.roll_contest", return_value=forced_roll):
            await ticker.tick(hours_advanced=8.0)

        assert victim.physical_status == "dead"
        # The dead victim's ACQUIRE goal never secured / completed.
        assert victim.life_goal.status is GoalStatus.ACTIVE
        assert victim.life_goal.last_outcome is None
