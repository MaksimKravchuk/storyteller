"""Real-model WorldChronicler smoke tests.

The Chronicler is deliberately conservative: most turns it should
return an empty :class:`ChroniclerResponse`. We assert (a) the call
succeeds and parses into the typed envelope, and (b) any
``thread_updates`` reference a UUID that actually exists on the input
``GameState`` — the Chronicler is documented to never invent thread
identifiers.
"""

from __future__ import annotations

from uuid import uuid4

import allure
import pytest

from cast.schemas.chronicler_response import ChroniclerResponse
from cast.schemas.turn_outputs import DialogueEntry, TurnOutputs
from cast.world_chronicler import WorldChronicler
from models.world_state import WorldThread
from tests import director_helpers
from tests.e2e._real_llm import real_llm_for


def _seed_thread(game_state, description: str) -> WorldThread:
    """Add an open thread to the game state and return it."""
    thread = WorldThread(
        uuid=uuid4(),
        description=description,
        category="political",
        introduced_scene=game_state.scene_number,
        status="open",
    )
    game_state.world_state.threads.append(thread)
    return thread


pytestmark = pytest.mark.live


@allure.epic("AI Agent Orchestration")
@allure.feature("WorldChronicler real-model world advancement")
class TestWorldChroniclerRealModel:
    @allure.story("Quiet turn returns valid schema")
    @allure.title("A real Chronicler on a quiet turn returns a structurally valid ChroniclerResponse")
    @pytest.mark.asyncio
    async def test_real_model_quiet_turn_returns_valid_response(self):
        game_state = director_helpers.make_game_state()
        chronicler = WorldChronicler(llm_client=real_llm_for("world_chronicler"), language="English")

        # A pure-wait turn with no dialogue, no new NPCs, no events —
        # the conservative path should produce mostly-empty fields.
        turn_outputs = TurnOutputs(wait=True, wait_reason="player rests for an hour")

        response = await chronicler.act(
            turn_outputs,
            {"game_state": game_state, "player_action": "Rest at the inn for an hour."},
        )

        assert isinstance(response, ChroniclerResponse)
        # Schema-shape contract: every list is a list, world_mood is
        # either ``None`` or a non-empty string.
        assert isinstance(response.new_threads, list)
        assert isinstance(response.thread_updates, list)
        assert isinstance(response.scheduled_events, list)
        assert isinstance(response.goal_drafts, list)
        if response.world_mood is not None:
            assert isinstance(response.world_mood, str)
            assert response.world_mood.strip(), "world_mood was set but empty"

    @allure.story("Thread updates reference existing UUIDs")
    @allure.title("A real Chronicler never invents thread UUIDs when advancing an existing thread")
    @pytest.mark.asyncio
    async def test_real_model_thread_updates_reference_existing_uuids(self):
        game_state = director_helpers.make_game_state()
        senate_thread = _seed_thread(game_state, "Whispers of a conspiracy in the Senate against the consul")

        chronicler = WorldChronicler(llm_client=real_llm_for("world_chronicler"), language="English")

        # A turn that obviously bears on the senate thread.
        turn_outputs = TurnOutputs(
            dialogue=[
                DialogueEntry(
                    npc_name="Brutus",
                    response="The consul will not see another sunrise. The dagger is decided.",
                ),
            ],
        )

        response = await chronicler.act(
            turn_outputs,
            {
                "game_state": game_state,
                "player_action": "Listen as Brutus reveals the conspirators' plan.",
            },
        )

        assert isinstance(response, ChroniclerResponse)
        # Input-tied: ANY thread_update the Chronicler emits must
        # reference a real UUID on the input game state. Failure mode
        # this catches: a hallucinated UUID would silently drop on the
        # applier floor in production. We only assert when the
        # Chronicler chose to emit updates — empty list is the
        # conservative default and equally valid.
        known_uuids = {thread.uuid for thread in game_state.world_state.threads}
        for update in response.thread_updates:
            assert update.thread_uuid in known_uuids, (
                "Chronicler emitted a thread_update referencing unknown UUID {0}; known UUIDs were {1}".format(
                    update.thread_uuid, sorted(known_uuids)
                )
            )
        # If the Chronicler did weigh in on this thread, the senate
        # thread is the most plausible target — soft assertion only:
        # log it for diagnostics, do not fail on a quiet response.
        if response.thread_updates:
            assert any(update.thread_uuid == senate_thread.uuid for update in response.thread_updates), (
                "Chronicler updated some thread but not the obviously-relevant senate thread {0}; updates: {1}".format(
                    senate_thread.uuid, response.thread_updates
                )
            )
