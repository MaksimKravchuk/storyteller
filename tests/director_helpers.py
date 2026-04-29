"""Shared factory functions for Director tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from cast.director import Director
from cast.schemas import action_plan as plan_mod
from knowledge.graph import KnowledgeGraph
from knowledge.memory import MemoryManager
from models import game_state as gs_mod, npc_card as npc_card_mod, scene as scene_mod, setting as setting_mod
from tests import actor_helpers
from tests._route_plan_builder import build_route_plan as route_plan
from tests.item_helpers import default_item_generator_execute
from timeline.event_manager import EventManager

actor_reply = actor_helpers.actor_reply
make_mock_actor = actor_helpers.make_mock_actor
GameState = gs_mod.GameState
NPCCard = npc_card_mod.NPCCard
Scene = scene_mod.Scene
SceneNPC = scene_mod.SceneNPC
Setting = setting_mod.Setting


def make_setting() -> Setting:
    """Create a minimal Setting for tests."""
    return Setting(
        name="Ancient Rome",
        time_period="1st century AD",
        region="Italy",
        summary="The Roman Empire.",
    )


def make_game_state() -> GameState:
    """Create a GameState with a default scene containing one guard NPC."""
    kg = KnowledgeGraph()
    gs = GameState(setting=make_setting(), knowledge_graph=kg)
    gs.current_scene = Scene(
        location_id="forum",
        description="The bustling Roman Forum.",
        npcs_present=[SceneNPC(role="guard", uuid="npc-1")],
        points_of_interest=[scene_mod.PointOfInterest(names=["fountain"]), scene_mod.PointOfInterest(names=["statue"])],
    )
    return gs


def make_mock_agent(return_value: object = None) -> AsyncMock:
    """Create a mock agent with both .act and .execute wired."""
    mock = AsyncMock()
    mock.act = AsyncMock(return_value=return_value)
    mock.execute = AsyncMock(return_value=return_value)
    return mock


def make_cast(narrator_response: str = "Narrated result.") -> dict[str, Any]:
    """Build a dict of mocked agents for Director construction."""
    item_gen = AsyncMock()
    item_gen.act = AsyncMock(side_effect=default_item_generator_execute)
    item_gen.execute = AsyncMock(side_effect=default_item_generator_execute)
    return {
        "scene_builder": make_mock_agent(
            Scene(
                location_id="new-loc",
                description="A new place.",
                npcs_present=[SceneNPC(role="merchant")],
            )
        ),
        "narrator": make_mock_agent(narrator_response),
        "npc_generator": make_mock_agent([]),
        "data_miner": AsyncMock(),
        "item_generator": item_gen,
    }


def _coerce_route_response(
    route_response: Any,
) -> plan_mod.ClarificationRequest | Any:
    """Normalise a test fixture's route_response into a typed plan.

    Accepts:

    - an already-typed ``ActionPlan`` / ``ClarificationRequest`` instance
      (pass-through),
    - a string action type (routed through :func:`route_plan`),
    - a legacy dict of the pre-tool-calls routing plan shape (converted
      field-by-field for backward compatibility with existing test
      fixtures; migrate new tests to build typed instances directly).
    """
    if isinstance(
        route_response,
        (
            plan_mod.ClarificationRequest,
            plan_mod.MovePlan,
            plan_mod.TalkPlan,
            plan_mod.ExaminePlan,
            plan_mod.InteractPlan,
            plan_mod.SleepPlan,
            plan_mod.WaitPlan,
            plan_mod.ExplorePlan,
            plan_mod.OtherPlan,
        ),
    ):
        return route_response
    if isinstance(route_response, str):
        return route_plan(route_response)
    if isinstance(route_response, dict):
        if route_response.get("needs_clarification"):
            return plan_mod.ClarificationRequest(
                question=route_response.get("clarification_question", ""),
                reason="",
            )
        action_type = route_response.get("action_type", "OTHER")
        contest_raw = route_response.get("contest")
        contest = plan_mod.Contest(**contest_raw) if contest_raw else None
        return route_plan(
            action_type,
            delegate=tuple(route_response.get("delegate_to") or ("narrator",)),
            targets=tuple(route_response.get("targets") or ()),
            intent=route_response.get("intent") or "test intent",
            is_aggressive=bool(route_response.get("is_aggressive")),
            contest=contest,
            direction=route_response.get("direction") or "forward",
            reason=route_response.get("reason") or "test",
            wait_reason=route_response.get("wait_reason"),
        )
    return route_response


def make_director(
    game_state: GameState | None = None,
    route_response: Any = None,
    narrator_response: str = "Narrated result.",
) -> Director:
    """Create a Director with mocked LLM and agents.

    ``route_response`` may be a typed ``ActionPlan`` / ``ClarificationRequest``
    instance (preferred), a string action type (routed through
    :func:`route_plan`), or a legacy dict matching the pre-tool-calls
    routing-plan shape (converted automatically so existing fixtures
    keep working). When ``None`` the router is left un-mocked.
    """
    gs = game_state or make_game_state()
    cast = make_cast(narrator_response)
    the_director = Director(
        llm_client=AsyncMock(),
        game_state=gs,
        event_manager=EventManager(game_state=gs, knowledge_graph=gs.knowledge_graph),
        memory_manager=MagicMock(spec=MemoryManager),
        scene_builder=cast["scene_builder"],
        narrator=cast["narrator"],
        npc_generator=cast["npc_generator"],
        data_miner=cast["data_miner"],
        item_generator=cast["item_generator"],
        language="English",
    )
    if route_response is not None:
        the_director._router.route_action = AsyncMock(  # type: ignore[method-assign]
            return_value=_coerce_route_response(route_response),
        )
    return the_director


def setup_npc(
    gs: GameState,
    uuid: str,
    name: str = "Guard",
    occupation: str = "city guard",
    **kwargs: Any,
) -> NPCCard:
    """Create an NPC, assign uuid and mood, register in game state."""
    mood = kwargs.pop("mood", "neutral")
    npc = NPCCard(name=name, occupation=occupation, **kwargs)
    npc.uuid = uuid
    npc.current_mood = mood
    gs.npcs[uuid] = npc
    return npc
