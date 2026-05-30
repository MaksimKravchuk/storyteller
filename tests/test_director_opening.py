"""Regression coverage for the synthetic opening turn (new-game creation).

The engine opens a new game by sending a synthetic ``_OPENING_SCENE_PROMPT``
through the Director. That prompt is engine-authored — the player has
addressed no NPC and has not yet acted — so the opening turn must only
*build and narrate* the scene. It must NOT:

* route the prompt through the LLM action router (which would otherwise
  classify "Look around … include an addressable NPC" as a TALK/target
  action),
* feed the synthetic prompt into an Actor via the dialogue path
  (``"Player is addressing you, <NPC>. Player action: Look around …"``),
* run NPC autonomous turns.

Before this fix each scene NPC's Actor fired twice on turn zero — once via
dialogue, once via the autonomous-turn pass — which is the reported
"calls actor twice when we create a new game" bug. These drive the real
``Director.act`` opening path and only stub the two methods that lead to
``actor.execute`` so the assertion is a true consumer-seam check.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast.schemas.action_plan import ExplorePlan
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from tests.director_helpers import make_director, make_setting

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Opening scene"),
]

_OPENING_PROMPT = (
    "Look around and describe the starting scene. For any premise involving social investigation, "
    "include at least one named, addressable NPC with a visible social affordance the player can act on."
)


def _fresh_game_state() -> GameState:
    """A brand-new game: no scene built yet, no NPCs registered."""
    return GameState(setting=make_setting(), knowledge_graph=KnowledgeGraph())


def _spy_actor_paths(director, *, route_plan: ExplorePlan) -> tuple[AsyncMock, AsyncMock, AsyncMock]:
    """Spy the router plus the two methods that ultimately call ``actor.execute``.

    ``DialogueHandler.handle_dialogue`` drives the dialogue Actor path,
    ``NPCTurnResolver.resolve_npc_turns`` drives the autonomous-turn Actor
    path, and ``ActionRouter.route_action`` is the LLM classifier the
    opening turn must skip. ``director`` is intentionally untyped so the
    method reassignments stay local to the seam; the returned mocks carry
    the assertion surface. The rest of the real ``execute_plan`` still runs.
    """
    dialogue_spy = AsyncMock(return_value=([], set()))
    npc_turn_spy = AsyncMock(return_value=[])
    route_spy = AsyncMock(return_value=route_plan)
    director._dialogue.handle_dialogue = dialogue_spy
    director._npc_turns.resolve_npc_turns = npc_turn_spy
    director._router.route_action = route_spy
    return dialogue_spy, npc_turn_spy, route_spy


@allure.story("Opening turn")
@allure.title("Opening turn builds and narrates the scene without invoking any NPC Actor path")
@pytest.mark.asyncio
async def test_opening_turn_does_not_invoke_npc_actors() -> None:
    director = make_director(game_state=_fresh_game_state(), narrator_response="Opening narration.")
    dialogue_spy, npc_turn_spy, route_spy = _spy_actor_paths(
        director,
        route_plan=ExplorePlan(intent="should not be used on the opening turn"),
    )

    narration = await director.execute(_OPENING_PROMPT, context={"opening": True})

    # Scene was built and narrated...
    assert narration == "Opening narration."
    assert director._game_state.current_scene is not None
    # ...but no Actor was driven, and the LLM router was bypassed entirely.
    npc_turn_spy.assert_not_awaited()
    dialogue_spy.assert_not_awaited()
    route_spy.assert_not_awaited()


@allure.story("Opening turn")
@allure.title("A normal (non-opening) turn still runs NPC autonomous turns")
@pytest.mark.asyncio
async def test_normal_turn_still_runs_npc_turns() -> None:
    """The opening suppression must be scoped to turn zero, not global."""
    director = make_director(game_state=_fresh_game_state(), narrator_response="A normal narration.")
    _dialogue_spy, npc_turn_spy, route_spy = _spy_actor_paths(
        director,
        route_plan=ExplorePlan(intent="player looks around"),
    )

    await director.execute("I look around the square.")

    route_spy.assert_awaited_once()
    npc_turn_spy.assert_awaited_once()
