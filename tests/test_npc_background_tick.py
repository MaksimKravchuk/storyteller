"""Unit tests for the off-scene NPC goal ticker."""

from __future__ import annotations

from unittest.mock import patch

import allure
import pytest

from cast import dice
from cast.npc_background_tick import NPCBackgroundTicker
from models.goal import Goal, GoalKind, GoalStatus
from models.location import Location
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from tests._uuid_helpers import make_uuid
from tests._aftermath_helpers import RecordingMemoryManager, make_actor_target_state, seed_kill_thread


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

        forced_roll = dice.ContestRoll(
            contest_type=dice.ContestType.COMBAT,
            outcome=dice.ContestOutcome.ACTOR_DOMINATES,
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
        memory = RecordingMemoryManager()

        ticker = NPCBackgroundTicker(state, memory)
        await ticker.tick(hours_advanced=8.0)

        assert actor.life_goal.turns_pursued == 1
        assert any("offscreen wait" in note for note in actor.life_goal.progress_notes)
        assert target.physical_status == "healthy"
        assert memory.calls == []
