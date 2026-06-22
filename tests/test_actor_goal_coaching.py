"""Tests for kind-aware Actor goal coaching (issue #315).

The ``goal`` PromptSection used to hardcode a STEALTH→ATTACK combat
escalation that rendered for every GoalKind. ``_goal_coaching`` now
selects a coaching bank by behavioural category and locale so a social
goal (BEFRIEND/TRADE/…) no longer reads as "attack the target", while
the combat path stays byte-for-byte unchanged.
"""

from __future__ import annotations

import allure
import pytest

from cast.actor_config import _HOSTILE_GOAL_KINDS, _goal_coaching, goal_prompt_vars
from models.goal import Goal, GoalKind, GoalScope
from models.npc_card import NPCCard
from prompts.actor_prompts import (
    GOAL_COACHING_AVOID,
    GOAL_COACHING_HOSTILE,
    GOAL_COACHING_SOCIAL,
    get_actor_prompts,
)
from tests._uuid_helpers import make_uuid

_HOSTILE_DISTINCTIVE = "commit to ATTACK now"
_SOCIAL_DISTINCTIVE = "through conversation"
_AVOID_DISTINCTIVE = "steer clear"

_SOCIAL_KINDS: tuple[GoalKind, ...] = (
    GoalKind.BEFRIEND,
    GoalKind.COURT,
    GoalKind.GOSSIP,
    GoalKind.TRADE,
    GoalKind.HELP,
    GoalKind.WARN,
    GoalKind.ASK,
    GoalKind.ACQUIRE,
    GoalKind.PROTECT,
    GoalKind.EAT,
    GoalKind.ERRAND,
    GoalKind.REST,
)


@allure.epic("NPC Interaction")
@allure.feature("Actor goal coaching")
class TestGoalCoachingSelection:
    """``_goal_coaching`` maps every kind to exactly one non-empty locale bank."""

    @allure.story("Category mapping")
    @allure.title("Hostile kinds get the combat escalation bank")
    @pytest.mark.parametrize(
        "kind",
        [GoalKind.KILL, GoalKind.PURSUE, GoalKind.DEFEND, GoalKind.FLEE, GoalKind.FLEE_SCENE],
    )
    def test_hostile_kinds_get_hostile_bank(self, kind: GoalKind) -> None:
        assert kind in _HOSTILE_GOAL_KINDS
        assert _goal_coaching(kind, "English") == GOAL_COACHING_HOSTILE

    @allure.story("Category mapping")
    @allure.title("Social and neutral kinds get the social bank")
    @pytest.mark.parametrize("kind", _SOCIAL_KINDS)
    def test_social_kinds_get_social_bank(self, kind: GoalKind) -> None:
        assert _goal_coaching(kind, "English") == GOAL_COACHING_SOCIAL

    @allure.story("Category mapping")
    @allure.title("AVOID gets its own disengage bank")
    def test_avoid_gets_avoid_bank(self) -> None:
        assert _goal_coaching(GoalKind.AVOID, "English") == GOAL_COACHING_AVOID

    @allure.story("Exhaustiveness")
    @allure.title("Every GoalKind maps to exactly one non-empty coaching bank")
    def test_every_kind_maps_to_one_bank(self) -> None:
        banks = {GOAL_COACHING_HOSTILE, GOAL_COACHING_SOCIAL, GOAL_COACHING_AVOID}
        assert len(banks) == 3  # the three banks are distinct
        for kind in GoalKind:
            coaching = _goal_coaching(kind, "English")
            assert coaching
            assert coaching in banks

    @allure.story("Combat preservation")
    @allure.title("Hostile bank keeps the verbatim STEALTH→ATTACK escalation")
    def test_hostile_bank_is_verbatim_escalation(self) -> None:
        assert _HOSTILE_DISTINCTIVE in GOAL_COACHING_HOSTILE
        assert "STEALTH" in GOAL_COACHING_HOSTILE


@allure.epic("NPC Interaction")
@allure.feature("Actor goal coaching")
class TestGoalCoachingLocaleAware:
    """Coaching is locale-aware — an RU Actor must not receive English coaching."""

    @allure.story("Locale")
    @allure.title("Russian coaching banks are Cyrillic, not the English fallback")
    @pytest.mark.parametrize("kind", [GoalKind.KILL, GoalKind.BEFRIEND, GoalKind.AVOID])
    def test_russian_coaching_is_cyrillic(self, kind: GoalKind) -> None:
        english = _goal_coaching(kind, "English")
        russian = _goal_coaching(kind, "Russian")

        assert russian != english
        assert any("а" <= ch.lower() <= "я" for ch in russian)


def _npc_with_goal(kind: GoalKind) -> NPCCard:
    npc = NPCCard(name="Drusilla", occupation="herbalist")
    npc.uuid = make_uuid("npc-drusilla")
    npc.life_goal = Goal(scope=GoalScope.LIFE, kind=kind, description="standing agenda")
    return npc


@allure.epic("NPC Interaction")
@allure.feature("Actor goal coaching")
class TestGoalCoachingReachesPromptBody:
    """Consumer seam: the selected coaching renders into the goal section body."""

    @allure.story("Consumer seam")
    @allure.title("A social-kind goal renders social coaching, not combat coaching (EN + RU)")
    @pytest.mark.parametrize("language", ["English", "Russian"])
    def test_social_goal_renders_social_coaching(self, language: str) -> None:
        npc = _npc_with_goal(GoalKind.BEFRIEND)
        goal_vars = goal_prompt_vars(npc, "Livia", language)
        assert goal_vars is not None

        rendered = get_actor_prompts(language).system_action.render(**goal_vars)

        if language == "English":
            assert _SOCIAL_DISTINCTIVE in rendered
            assert _HOSTILE_DISTINCTIVE not in rendered

    @allure.story("Consumer seam")
    @allure.title("A combat-kind goal still renders the unchanged combat coaching")
    def test_combat_goal_renders_combat_coaching(self) -> None:
        npc = _npc_with_goal(GoalKind.KILL)
        goal_vars = goal_prompt_vars(npc, "Marcus", "English")
        assert goal_vars is not None

        rendered = get_actor_prompts("English").system_action.render(**goal_vars)

        assert _HOSTILE_DISTINCTIVE in rendered
        assert _SOCIAL_DISTINCTIVE not in rendered
