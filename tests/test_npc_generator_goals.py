"""Tests for NPCGenerator life-tier goal emission and the helper module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest
from loguru import logger

from cast._npc_generator_goals import build_life_goal, candidate_goal_targets
from cast.npc_generator import NPCGenerator
from cast.schemas.npc_response import NPCAttributes, NPCGoalDraft, NPCResponse
from models.goal import GoalKind, GoalScope
from models.npc_card import NPCCard
from tests._uuid_helpers import make_uuid

_MARCUS = make_uuid("npc-marcus")

_SEND_JSON = "_send_json"


def _payload(name: str, goal: NPCGoalDraft | None = None) -> NPCResponse:
    return NPCResponse(
        name=name,
        biography="{0} bio".format(name),
        appearance="tall",
        short_descriptor="a tall figure in plain cloth",
        occupation="legionary",
        personality_traits=["stern"],
        speech_style="gruff",
        knowledge_scope="city",
        attributes=NPCAttributes(combat_skill=7),
        inventory=[],
        goal=goal,
    )


def _seed_marcus(game_state) -> NPCCard:
    """Add a Marcus NPC to ``game_state`` so KILL goals have a real target."""
    marcus = NPCCard(name="Marcus", occupation="merchant")
    marcus.uuid = _MARCUS
    game_state.npcs[marcus.uuid] = marcus
    return marcus


@allure.epic("NPC Interaction")
@allure.feature("NPC Generator")
class TestGoalApplier:
    """``build_life_goal`` filters draft → :class:`Goal` with target resolution."""

    @allure.story("Goal building")
    @allure.title("Valid KILL draft resolves to a life-tier Goal targeting the named NPC")
    def test_kill_draft_resolves_target(self, game_state) -> None:
        marcus = _seed_marcus(game_state)
        draft = NPCGoalDraft(kind=GoalKind.KILL, description="avenge brother", target_name="marcus")

        goal = build_life_goal(draft, game_state, "vengeful brother")

        assert goal is not None
        assert goal.scope is GoalScope.LIFE
        assert goal.kind is GoalKind.KILL
        assert goal.target_uuid == marcus.uuid

    @allure.story("Goal building")
    @allure.title("Social standing kinds resolve to a life-tier Goal targeting the named NPC")
    @pytest.mark.parametrize(
        "kind",
        [
            GoalKind.BEFRIEND,
            GoalKind.COURT,
            GoalKind.GOSSIP,
            GoalKind.TRADE,
            GoalKind.HELP,
            GoalKind.WARN,
            GoalKind.ASK,
        ],
    )
    def test_social_creation_kinds_accepted(self, game_state, kind: GoalKind) -> None:
        marcus = _seed_marcus(game_state)
        draft = NPCGoalDraft(kind=kind, description="standing agenda", target_name="Marcus")

        goal = build_life_goal(draft, game_state, "townsperson")

        assert goal is not None
        assert goal.scope is GoalScope.LIFE
        assert goal.kind is kind
        assert goal.target_uuid == marcus.uuid

    @allure.story("Goal building")
    @allure.title("ACQUIRE is a valid generator life goal (standing material ambition)")
    def test_acquire_kind_accepted(self, game_state) -> None:
        marcus = _seed_marcus(game_state)
        draft = NPCGoalDraft(kind=GoalKind.ACQUIRE, description="amass a fortune", target_name="Marcus")

        goal = build_life_goal(draft, game_state, "merchant")

        assert goal is not None
        assert goal.kind is GoalKind.ACQUIRE
        assert goal.target_uuid == marcus.uuid

    @allure.story("Goal building")
    @allure.title("AVOID is Chronicler-only — dropped at creation with a logged warning")
    def test_avoid_kind_dropped_at_creation(self, game_state) -> None:
        _seed_marcus(game_state)
        draft = NPCGoalDraft(kind=GoalKind.AVOID, description="steer clear", target_name="Marcus")

        captured: list[str] = []
        sink_id = logger.add(captured.append, level="WARNING")
        try:
            result = build_life_goal(draft, game_state, "wary trader")
        finally:
            logger.remove(sink_id)

        assert result is None
        assert any("avoid" in line for line in captured)

    @allure.story("Goal building")
    @allure.title("Tactical-tier and excluded life kinds are dropped at creation time")
    @pytest.mark.parametrize(
        "kind",
        [
            GoalKind.DEFEND,
            GoalKind.EAT,
            GoalKind.ERRAND,
            GoalKind.REST,
            GoalKind.FLEE_SCENE,
            GoalKind.FLEE,
        ],
    )
    def test_tactical_kind_rejected(self, game_state, kind: GoalKind) -> None:
        _seed_marcus(game_state)
        draft = NPCGoalDraft(kind=kind, description="hit back", target_name="Marcus")

        assert build_life_goal(draft, game_state, "guard") is None

    @allure.story("Goal building")
    @allure.title("Unresolvable target_name causes the goal to be dropped")
    def test_unresolved_target_dropped(self, game_state) -> None:
        draft = NPCGoalDraft(kind=GoalKind.KILL, description="hunt", target_name="ghost")

        assert build_life_goal(draft, game_state, "hunter") is None

    @allure.story("Goal building")
    @allure.title("PROTECT goal without a target is allowed (target_uuid stays None)")
    def test_protect_without_target_allowed(self, game_state) -> None:
        draft = NPCGoalDraft(kind=GoalKind.PROTECT, description="guard the village")

        goal = build_life_goal(draft, game_state, "village elder")

        assert goal is not None
        assert goal.target_uuid is None


@allure.epic("NPC Interaction")
@allure.feature("NPC Generator")
class TestCandidateTargets:
    """``candidate_goal_targets`` lists the NPCs the LLM may reference by name."""

    @allure.story("Candidate listing")
    @allure.title("All registered NPC names are candidate targets")
    def test_lists_registered_names(self, game_state) -> None:
        _seed_marcus(game_state)
        targets = candidate_goal_targets(game_state)
        assert "Marcus" in targets


@allure.epic("NPC Interaction")
@allure.feature("NPC Generator")
class TestGeneratorGoalIntegration:
    """End-to-end: NPCGenerator.act applies emitted goals with per-batch rate limit."""

    @pytest.mark.asyncio
    @allure.story("Goal emission")
    @allure.title("Generator attaches the LLM's goal block to the produced NPCCard.life_goal")
    async def test_goal_attached_to_card(self, game_state) -> None:
        _seed_marcus(game_state)
        gen = NPCGenerator(llm_client=MagicMock())
        goal_draft = NPCGoalDraft(kind=GoalKind.KILL, description="avenge brother", target_name="Marcus")
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[_payload("Brutus", goal=goal_draft)])):
            cards = await gen.act(["vengeful brother"], {"game_state": game_state})

        card = cards[0]
        assert card.life_goal is not None
        assert card.life_goal.kind is GoalKind.KILL
        assert card.life_goal.target_uuid == _MARCUS

    @pytest.mark.asyncio
    @allure.story("Rate limit")
    @allure.title("Per-batch rate limit caps life-goal emission at one card per act() call")
    async def test_rate_limit_caps_at_one(self, game_state) -> None:
        _seed_marcus(game_state)
        gen = NPCGenerator(llm_client=MagicMock())
        goal_draft = NPCGoalDraft(kind=GoalKind.KILL, description="avenge brother", target_name="Marcus")
        payloads = [
            _payload("Brutus", goal=goal_draft),
            _payload("Cassius", goal=goal_draft),
        ]
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=payloads)):
            cards = await gen.act(["brother A", "brother B"], {"game_state": game_state})

        with_goal = [card for card in cards if card.life_goal is not None]
        assert len(with_goal) == 1
        assert with_goal[0].name == "Brutus"

    @pytest.mark.asyncio
    @allure.story("Goal emission")
    @allure.title("LLM with no goal block leaves card.life_goal as None")
    async def test_no_goal_when_omitted(self, game_state) -> None:
        gen = NPCGenerator(llm_client=MagicMock())
        with patch.object(gen, _SEND_JSON, new=AsyncMock(side_effect=[_payload("Aulus")])):
            cards = await gen.act(["bard"], {"game_state": game_state})
        assert cards[0].life_goal is None
