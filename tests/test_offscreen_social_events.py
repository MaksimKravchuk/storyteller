"""Tests for off-screen social memory and follow-on goal write-back."""

from __future__ import annotations

from typing import cast

import allure
import pytest

from cast.director_events import EventProcessor
from knowledge.memory import MemoryManager
from knowledge import salience as salience_presets
from knowledge.node import KnowledgeScope
from models.goal import Goal, GoalKind
from timeline.event import EventEffect, GameEvent
from timeline.event_manager import EventManager
from tests._aftermath_helpers import RecordingMemoryManager, make_actor_target_state


_SOCIAL_EFFECT = "SOCIAL_MEMORY"


def _processor_with_memory(state, memory: RecordingMemoryManager) -> EventProcessor:
    event_mgr = EventManager(game_state=state, knowledge_graph=state.knowledge_graph)
    return EventProcessor(state, event_mgr, cast(MemoryManager, memory))


def _remote_event(effect: EventEffect, location_id) -> GameEvent:
    return GameEvent(
        name="off-screen social consequence",
        scheduled_at=float(0),
        duration=1.0,
        location_id=location_id,
        scope="local",
        effects=[effect],
        on_complete_description="A private off-screen encounter has consequences.",
    )


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
        effect = EventEffect(
            effect_type=_SOCIAL_EFFECT,
            target_id=str(target.uuid),
            effect_data={"actor_id": str(actor.uuid), "target_id": str(target.uuid), "kind": "harm"},
        )

        await _processor_with_memory(state, memory).process_remote_events([_remote_event(effect, location.uuid)])

        assert len(memory.calls) == 2
        social_call = memory.calls[1]
        assert "grudge" in social_call["event_description"]
        assert social_call["scope"] is KnowledgeScope.LOCAL
        assert social_call["location_id"] == location.uuid
        assert social_call["salience"] == pytest.approx(salience_presets.RETALIATION)
        assert set(social_call["witness_ids"]) == {actor.uuid, target.uuid}
        assert target.life_goal is not None
        assert target.life_goal.kind is GoalKind.KILL
        assert target.life_goal.target_uuid == actor.uuid

    @pytest.mark.asyncio
    @allure.story("Debt event")
    @allure.title("Off-screen kindness creates a debt memory and HELP follow-on goal")
    async def test_kindness_event_creates_memory_and_help_goal(self) -> None:
        state, actor, target, location = make_actor_target_state()
        target.life_goal = None
        memory = RecordingMemoryManager()
        effect = EventEffect(
            effect_type=_SOCIAL_EFFECT,
            target_id=str(target.uuid),
            effect_data={"actor_id": str(actor.uuid), "target_id": str(target.uuid), "kind": "kindness"},
        )

        await _processor_with_memory(state, memory).process_remote_events([_remote_event(effect, location.uuid)])

        assert len(memory.calls) == 2
        social_call = memory.calls[1]
        assert "debt" in social_call["event_description"]
        assert social_call["scope"] is KnowledgeScope.LOCAL
        assert social_call["salience"] == pytest.approx(salience_presets.REMOTE_EVENT)
        assert target.life_goal is not None
        assert target.life_goal.kind is GoalKind.HELP
        assert target.life_goal.target_uuid == actor.uuid

    @pytest.mark.asyncio
    @allure.story("Compatibility")
    @allure.title("Social follow-on goals do not overwrite an active vendetta")
    async def test_social_event_does_not_overwrite_active_life_goal(self) -> None:
        state, actor, target, location = make_actor_target_state()
        existing = Goal(kind=GoalKind.PURSUE, description="track someone else")
        target.life_goal = existing
        memory = RecordingMemoryManager()
        effect = EventEffect(
            effect_type=_SOCIAL_EFFECT,
            target_id=str(target.uuid),
            effect_data={"actor_id": str(actor.uuid), "target_id": str(target.uuid), "kind": "kindness"},
        )

        await _processor_with_memory(state, memory).process_remote_events([_remote_event(effect, location.uuid)])

        assert len(memory.calls) == 2
        assert target.life_goal is existing
