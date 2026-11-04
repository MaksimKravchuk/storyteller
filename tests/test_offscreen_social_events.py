"""Tests for off-screen social memory and follow-on goal write-back."""

from __future__ import annotations

import asyncio
from typing import Any, cast

import allure
import pytest

from cast import _npc_social_events as npc_social_events, director_events
from cast.schemas.chronicler_response import ScheduledEventDraft
from knowledge import charge as charge_presets, memory as memory_mod, node as node_mod, salience as salience_presets
from models import goal as goal_mod, relationship as relationship_mod
from tests._aftermath_helpers import RecordingMemoryManager, make_actor_target_state
from timeline import event as event_mod, event_manager as event_manager_mod


_SOCIAL_EFFECT = "SOCIAL_MEMORY"


def _processor_with_memory(state, memory: RecordingMemoryManager) -> director_events.EventProcessor:
    event_mgr = event_manager_mod.EventManager(game_state=state, knowledge_graph=state.knowledge_graph)
    return director_events.EventProcessor(state, event_mgr, cast(memory_mod.MemoryManager, memory))


def _remote_event(effect: event_mod.EventEffect, location_id) -> event_mod.GameEvent:
    return event_mod.GameEvent(
        name="off-screen social consequence",
        scheduled_at=float(0),
        duration=1.0,
        location_id=location_id,
        scope="local",
        effects=[effect],
        on_complete_description="A private off-screen encounter has consequences.",
    )


class DelayedSocialMemoryManager(RecordingMemoryManager):
    """Capture calls while making one social memory write finish later."""

    def __init__(self, delayed_outcome: str) -> None:
        super().__init__()
        self._delayed_outcome = delayed_outcome

    async def create_memory_from_event(self, event: Any):
        if event.slots.outcome == self._delayed_outcome:
            await asyncio.sleep(0.01)
        return await super().create_memory_from_event(event)


@allure.epic("NPC Interaction")
@allure.feature("Off-screen social write-back")
class TestOffScreenSocialEvents:
    """Remote social event effects persist memories and seed follow-on goals."""

    @pytest.mark.asyncio
    @allure.story("Grudge event")
    @allure.title("Off-screen harm creates a grudge memory and KILL follow-on goal")
    async def test_harm_event_creates_memory_and_kill_goal(self) -> None:
        state, actor, target, location = make_actor_target_state()
        target.life_goal = None
        memory = RecordingMemoryManager()
        effect = event_mod.EventEffect(
            effect_type=_SOCIAL_EFFECT,
            target_id=str(target.uuid),
            effect_data={"actor_id": str(actor.uuid), "target_id": str(target.uuid), "kind": "harm"},
        )
        event = _remote_event(effect, location.uuid)

        await _processor_with_memory(state, memory).process_remote_events([event])

        assert len(memory.calls) == 2
        social_call = memory.calls[1]
        assert "grudge" in social_call["event_description"]
        assert social_call["scope"] is node_mod.KnowledgeScope.LOCAL
        assert social_call["location_id"] == location.uuid
        assert social_call["salience"] == pytest.approx(salience_presets.RETALIATION)
        assert social_call["valence"] == pytest.approx(charge_presets.RETALIATION.base_valence)
        assert social_call["charge_intensity"] == pytest.approx(charge_presets.RETALIATION.base_intensity)
        assert social_call["charge_category"] == charge_presets.RETALIATION.category
        assert social_call["subject_id"] == actor.uuid
        assert set(social_call["tags"]) == {
            "social_memory",
            "social_memory:harm",
            "social_memory:grudge",
            f"actor:{actor.uuid}",
            f"target:{target.uuid}",
            f"source_event:{event.uuid}",
        }
        assert set(social_call["witness_ids"]) == {actor.uuid, target.uuid}
        assert target.life_goal is not None
        assert target.life_goal.kind is goal_mod.GoalKind.KILL
        assert target.life_goal.target_uuid == actor.uuid

    @pytest.mark.asyncio
    @allure.story("Debt event")
    @allure.title("Off-screen kindness creates a debt memory and HELP follow-on goal")
    async def test_kindness_event_creates_memory_and_help_goal(self) -> None:
        state, actor, target, location = make_actor_target_state()
        target.life_goal = None
        memory = RecordingMemoryManager()
        effect = event_mod.EventEffect(
            effect_type=_SOCIAL_EFFECT,
            target_id=str(target.uuid),
            effect_data={"actor_id": str(actor.uuid), "target_id": str(target.uuid), "kind": "kindness"},
        )

        await _processor_with_memory(state, memory).process_remote_events([_remote_event(effect, location.uuid)])

        assert len(memory.calls) == 2
        social_call = memory.calls[1]
        assert "debt" in social_call["event_description"]
        assert social_call["scope"] is node_mod.KnowledgeScope.LOCAL
        assert social_call["salience"] == pytest.approx(salience_presets.REMOTE_EVENT)
        assert target.life_goal is not None
        assert target.life_goal.kind is goal_mod.GoalKind.HELP
        assert target.life_goal.target_uuid == actor.uuid

    @pytest.mark.asyncio
    @allure.story("Compatibility")
    @allure.title("Social follow-on goals do not overwrite an active vendetta")
    async def test_social_event_does_not_overwrite_active_life_goal(self) -> None:
        state, actor, target, location = make_actor_target_state()
        existing = goal_mod.Goal(kind=goal_mod.GoalKind.PURSUE, description="track someone else")
        target.life_goal = existing
        memory = RecordingMemoryManager()
        effect = event_mod.EventEffect(
            effect_type=_SOCIAL_EFFECT,
            target_id=str(target.uuid),
            effect_data={"actor_id": str(actor.uuid), "target_id": str(target.uuid), "kind": "kindness"},
        )

        await _processor_with_memory(state, memory).process_remote_events([_remote_event(effect, location.uuid)])

        assert len(memory.calls) == 2
        assert target.life_goal is existing

    @pytest.mark.asyncio
    @allure.story("Local completion")
    @allure.title("Local SOCIAL_MEMORY completions still persist social write-back")
    async def test_local_social_event_creates_memory_and_goal(self) -> None:
        state, actor, target, location = make_actor_target_state()
        target.life_goal = None
        memory = RecordingMemoryManager()
        effect = event_mod.EventEffect(
            effect_type=_SOCIAL_EFFECT,
            target_id=str(target.uuid),
            effect_data={"actor_id": str(actor.uuid), "target_id": str(target.uuid), "kind": "harm"},
        )

        await npc_social_events.process_social_effects(
            [_remote_event(effect, location.uuid)], state, cast(memory_mod.MemoryManager, memory)
        )

        assert len(memory.calls) == 1
        assert "grudge" in memory.calls[0]["event_description"]
        assert target.life_goal is not None
        assert target.life_goal.kind is goal_mod.GoalKind.KILL

    @pytest.mark.asyncio
    @allure.story("Deterministic ordering")
    @allure.title("Earlier SOCIAL_MEMORY events choose the follow-on goal deterministically")
    async def test_social_goal_uses_event_order_not_memory_completion_order(self) -> None:
        state, actor, target, location = make_actor_target_state()
        target.life_goal = None
        memory = DelayedSocialMemoryManager(delayed_outcome="debt")
        kindness = event_mod.EventEffect(
            effect_type=_SOCIAL_EFFECT,
            target_id=str(target.uuid),
            effect_data={"actor_id": str(actor.uuid), "target_id": str(target.uuid), "kind": "kindness"},
        )
        harm = event_mod.EventEffect(
            effect_type=_SOCIAL_EFFECT,
            target_id=str(target.uuid),
            effect_data={"actor_id": str(actor.uuid), "target_id": str(target.uuid), "kind": "harm"},
        )

        await _processor_with_memory(state, memory).process_remote_events(
            [_remote_event(kindness, location.uuid), _remote_event(harm, location.uuid)],
        )

        assert target.life_goal is not None
        assert target.life_goal.kind is goal_mod.GoalKind.HELP

    @allure.story("Chronicler scheduling")
    @allure.title("ScheduledEventDraft effects reach the scheduled GameEvent")
    def test_schedule_drafts_preserves_social_memory_effects(self) -> None:
        state, actor, target, location = make_actor_target_state()
        memory = RecordingMemoryManager()
        event_mgr = event_manager_mod.EventManager(game_state=state, knowledge_graph=state.knowledge_graph)
        draft = ScheduledEventDraft.model_validate(
            {
                "name": "Marcus owes Brutus",
                "hours_from_now": 2.0,
                "location_id": location.uuid,
                "scope": "remote",
                "effects": [
                    {
                        "effect_type": _SOCIAL_EFFECT,
                        "actor_id": actor.uuid,
                        "target_id": target.uuid,
                        "kind": "kindness",
                    },
                ],
            },
        )

        director_events.EventProcessor(state, event_mgr, cast(memory_mod.MemoryManager, memory)).schedule_drafts(
            [draft], now=5.0
        )

        scheduled = event_mgr.get_pending_events()
        assert len(scheduled) == 1
        assert scheduled[0].effects[0].effect_type == _SOCIAL_EFFECT
        assert scheduled[0].effects[0].target_id == str(target.uuid)
        assert scheduled[0].effects[0].effect_data == {
            "actor_id": str(actor.uuid),
            "target_id": str(target.uuid),
            "kind": "kindness",
        }


async def _relationship_after(kind: str) -> relationship_mod.Relationship:
    state, actor, target, location = make_actor_target_state()
    effect = event_mod.EventEffect(
        effect_type=_SOCIAL_EFFECT,
        target_id=str(target.uuid),
        effect_data={"actor_id": str(actor.uuid), "target_id": str(target.uuid), "kind": kind},
    )
    memory = RecordingMemoryManager()
    await _processor_with_memory(state, memory).process_remote_events([_remote_event(effect, location.uuid)])
    return next(rel for rel in target.relationships if rel.target_uuid == str(actor.uuid))


@allure.epic("NPC Interaction")
@allure.feature("Off-screen social write-back")
class TestOffScreenSocialRelationships:
    """Remote social events move the target's directed relationship toward the actor."""

    @pytest.mark.asyncio
    @allure.story("Grudge event")
    @allure.title("Off-screen harm drops the target's relationship to ENEMY")
    async def test_harm_lowers_relationship(self) -> None:
        rel = await _relationship_after("harm")
        assert rel.kind is relationship_mod.RelationshipKind.ENEMY
        assert rel.intensity == -2

    @pytest.mark.asyncio
    @allure.story("Debt event")
    @allure.title("Off-screen kindness raises the target's relationship to ALLY")
    async def test_kindness_raises_relationship(self) -> None:
        rel = await _relationship_after("kindness")
        assert rel.kind is relationship_mod.RelationshipKind.ALLY
        assert rel.intensity == 2
