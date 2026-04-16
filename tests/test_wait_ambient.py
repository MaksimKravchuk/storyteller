"""Tests for the rich WAIT ambient context path (KER-20 / Fix 5).

Two levels of coverage:

1. **Director level** — runs ``director.act("wait")`` through a mocked
   ``DirectorCast`` (including a mocked ``world_chronicler``) and
   asserts the ``TurnOutputs`` handed to the Narrator carry a populated
   :class:`WaitContext` with the seeded threads, on-shift NPCs, and
   soon-firing events.

2. **Narrator level** — feeds a pre-built :class:`WaitContext` directly
   into a real :class:`Narrator` instance with a mocked LLM client and
   asserts the rendered user prompt surfaces ``wait_context_lines`` and
   ``hours_waited`` — i.e. the new ``PromptSection`` fired.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast.narrator import Narrator
from cast.schemas.chronicler_response import ChroniclerResponse
from cast.schemas.turn_outputs import TurnOutputs, WaitContext
from models.location import Location
from models.world_state import WorldThread
from tests.director_helpers import make_director, make_game_state, make_mock_agent, setup_npc
from timeline.event import GameEvent

_FORUM = "forum"
_NPC_MERCHANT = "npc-1"
_PLAYER_ACTION = "player_action"
_GAME_STATE = "game_state"
_MESSAGES = "messages"


def _wait_route() -> dict:
    return {
        "action_type": "WAIT",
        "is_aggressive": False,
        "targets": [],
        "needs_clarification": False,
        "delegate_to": ["narrator"],
    }


def _seed_forum_state():
    """Return a GameState whose player is in a registered ``forum`` location.

    ``make_game_state`` already builds a scene at ``location_id="forum"``
    with one ``SceneNPC(role="guard", uuid="npc-1")``. We extend it
    with a matching :class:`Location` entry, a pre-advanced clock that
    puts the game in morning (hour 10), and register the NPC so the
    on-shift collector has a real :class:`NPCCard` to inspect.
    """
    gs = make_game_state()
    gs.player.location_id = _FORUM
    gs.locations[_FORUM] = Location(
        name="Forum Romanum",
        description="A bustling plaza.",
        npcs_present=[_NPC_MERCHANT],
    )
    # Advance the clock into morning (hour 10). WAIT only adds 0.1 h,
    # so the merchant schedule stays in its "present" slot for the turn.
    gs.advance_clock(10.0)
    return gs


def _chronicler_mock():
    """Return a mocked ``world_chronicler`` that produces an empty response."""
    return make_mock_agent(ChroniclerResponse())


def _make_narrator() -> Narrator:
    llm_client = AsyncMock()
    llm_client.send_message = AsyncMock(
        return_value=AsyncMock(
            body="Narrated text.",
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        ),
    )
    return Narrator(llm_client=llm_client, language="English")


def _last_user_message(narrator: Narrator) -> str:
    """Extract the last user-role message sent to the mocked LLM."""
    send_call = narrator.llm_client.send_message.call_args  # type: ignore[attr-defined]
    return send_call.kwargs[_MESSAGES][-1].body


def _last_narrator_input(director) -> TurnOutputs:
    """Return the ``TurnOutputs`` most recently handed to the mocked Narrator."""
    narrator_call = director._cast.narrator.execute.call_args
    return narrator_call.kwargs["input_data"]


@allure.epic("Game Timeline")
@allure.feature("Wait action")
@allure.story("Rich ambient context")
class TestWaitContextPopulation:
    @allure.title(
        "WAIT turn populates raw_outputs.wait_context with threads, on-shift NPCs, and imminent events",
    )
    @pytest.mark.asyncio
    async def test_wait_context_is_populated(self):
        gs = _seed_forum_state()
        setup_npc(gs, _NPC_MERCHANT, name="Marcus", occupation="merchant")
        gs.world_state.threads.append(
            WorldThread(
                description="Grain shipments are delayed",
                category="economic",
                introduced_scene=0,
                involved_locations=[_FORUM],
            ),
        )

        director = make_director(game_state=gs, route_response=_wait_route())
        director._cast.world_chronicler = _chronicler_mock()
        director._deps.event_manager.schedule(
            GameEvent(
                name="market bell rings",
                scheduled_at=gs.game_clock,
                duration=0.5,
                location_id=_FORUM,
                scope="local",
                on_complete_description="The market bell rings across the plaza",
            ),
        )

        await director.act("wait")

        ctx = _last_narrator_input(director).wait_context
        assert ctx is not None
        assert any("Grain shipments" in thread.description for thread in ctx.active_threads)
        assert any("Marcus" in label for label in ctx.on_shift_npcs)
        assert any("market bell" in line for line in ctx.imminent_events)
        assert ctx.hours_waited > 0

    @allure.title("WAIT turn re-invokes the World Chronicler so threads and mood can advance")
    @pytest.mark.asyncio
    async def test_wait_invokes_world_chronicler(self):
        gs = _seed_forum_state()
        setup_npc(gs, _NPC_MERCHANT, name="Marcus", occupation="merchant")

        director = make_director(game_state=gs, route_response=_wait_route())
        chronicler = _chronicler_mock()
        director._cast.world_chronicler = chronicler

        await director.act("wait")

        chronicler.execute.assert_called_once()

    @allure.title("WAIT turn filters off-shift NPCs out of wait_context.on_shift_npcs")
    @pytest.mark.asyncio
    async def test_off_shift_npcs_are_excluded(self):
        gs = _seed_forum_state()
        # Push the clock into evening (hour 22) — merchants go home at
        # dusk per _MARKET_SCHEDULE, so the collector should drop them.
        gs.advance_clock(12.0)
        assert gs.game_time == "evening"
        setup_npc(gs, _NPC_MERCHANT, name="Marcus", occupation="merchant")

        director = make_director(game_state=gs, route_response=_wait_route())
        director._cast.world_chronicler = _chronicler_mock()

        await director.act("wait")

        ctx = _last_narrator_input(director).wait_context
        assert ctx is not None
        assert ctx.on_shift_npcs == []

    @allure.title(
        "WAIT turn filters world threads by player location so unrelated threads stay out of the ambient context",
    )
    @pytest.mark.asyncio
    async def test_threads_filtered_by_player_location(self):
        gs = _seed_forum_state()
        setup_npc(gs, _NPC_MERCHANT, name="Marcus", occupation="merchant")
        gs.world_state.threads.extend(
            [
                WorldThread(
                    description="Riot in the harbour district",
                    category="political",
                    introduced_scene=0,
                    involved_locations=["harbour"],
                ),
                WorldThread(
                    description="Grain shipments are delayed",
                    category="economic",
                    introduced_scene=0,
                    involved_locations=[_FORUM],
                ),
            ],
        )

        director = make_director(game_state=gs, route_response=_wait_route())
        director._cast.world_chronicler = _chronicler_mock()

        await director.act("wait")

        ctx = _last_narrator_input(director).wait_context
        assert ctx is not None
        assert len(ctx.active_threads) == 1
        assert "Grain shipments" in ctx.active_threads[0].description


@allure.epic("Narrative Delivery")
@allure.feature("Narrator")
@allure.story("Rich ambient context")
class TestNarratorRendersWaitContext:
    @allure.title(
        "Narrator prompt surfaces wait_context_lines and hours_waited when TurnOutputs carries a WaitContext",
    )
    @pytest.mark.asyncio
    async def test_narrator_prompt_includes_wait_context(self):
        narrator = _make_narrator()
        gs = make_game_state()
        wait_ctx = WaitContext(
            active_threads=[
                WorldThread(
                    description="Grain shipments are delayed",
                    category="economic",
                    introduced_scene=0,
                    involved_locations=[_FORUM],
                ),
            ],
            on_shift_npcs=["Marcus (merchant)"],
            imminent_events=["The market bell rings across the plaza"],
            hours_waited=0.1,
        )

        await narrator.act(
            input_data=TurnOutputs(wait=True, wait_context=wait_ctx),
            context={_PLAYER_ACTION: "wait", _GAME_STATE: gs},
        )

        user_msg = _last_user_message(narrator)
        assert "Grain shipments" in user_msg
        assert "Marcus (merchant)" in user_msg
        assert "market bell" in user_msg
        assert "0.1 hours" in user_msg
        # The new prompt section must have fired.
        assert "Do NOT write 'nothing happens'" in user_msg

    @allure.title("Narrator still produces the stub wait line when wait_context is None")
    @pytest.mark.asyncio
    async def test_narrator_falls_back_to_stub_without_wait_context(self):
        narrator = _make_narrator()
        gs = make_game_state()

        await narrator.act(
            input_data=TurnOutputs(wait=True),
            context={_PLAYER_ACTION: "wait", _GAME_STATE: gs},
        )

        user_msg = _last_user_message(narrator)
        assert "waits and observes" in user_msg
