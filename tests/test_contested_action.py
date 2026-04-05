"""Tests for build_contested_action — extends combat to social/stealth contests."""

from __future__ import annotations

import random

import pytest

from cast.dice import ContestOutcome, ContestType
from cast.director_dialogue_helpers import build_contested_action
from models.npc_card import NPCCard

_GUARD = "Guard"
_MERCHANT = "Merchant"
_COMBAT_SKILL = "combat_skill"
_PERSUASION_SKILL = "persuasion_skill"
_DECEPTION_SKILL = "deception_skill"
_INTIMIDATION_SKILL = "intimidation_skill"
_PERCEPTION_SKILL = "perception_skill"

_RNG_SEED = 57005
_DICE_MARKER = "[DICE ROLL:"
_STATUS_TAG = "[STATUS:"
_OUTCOME_MARKER = "OUTCOME:"


def _make_npc(name: str = _GUARD, **kwargs) -> NPCCard:
    return NPCCard(name=name, occupation="guard", **kwargs)


class TestBuildContestedActionCombat:
    """Aggressive actions produce combat contest rolls (backward-compat)."""

    def test_aggressive_produces_combat_roll(self):
        npc = _make_npc(attributes={_COMBAT_SKILL: 5})
        text, roll = build_contested_action("slash the guard", npc, is_aggressive=True, _rng=random.Random(_RNG_SEED))
        assert roll is not None
        assert roll.contest_type == ContestType.COMBAT
        assert _DICE_MARKER in text
        assert _OUTCOME_MARKER in text

    def test_non_aggressive_no_roll(self):
        npc = _make_npc()
        text, roll = build_contested_action("hello guard", npc, is_aggressive=False)
        assert roll is None
        assert text == "hello guard"

    def test_player_succeeds_includes_status_hint(self):
        npc = _make_npc(attributes={_COMBAT_SKILL: 0})
        for seed in range(200):
            rng = random.Random(seed)
            text, roll = build_contested_action("attack guard", npc, is_aggressive=True, _rng=rng)
            if roll and roll.outcome == ContestOutcome.ACTOR_SUCCEEDS:
                assert _STATUS_TAG in text
                return
        pytest.skip("No seed produced ACTOR_SUCCEEDS")

    def test_target_resists_no_status_hint(self):
        npc = _make_npc(attributes={_COMBAT_SKILL: 10})
        for seed in range(200):
            rng = random.Random(seed)
            text, roll = build_contested_action("attack guard", npc, is_aggressive=True, _rng=rng)
            if roll and roll.outcome in (ContestOutcome.TARGET_RESISTS, ContestOutcome.TARGET_DOMINATES):
                assert _STATUS_TAG not in text
                return
        pytest.skip("No seed produced target winning")


class TestBuildContestedActionSocial:
    """Contest info from routing plan produces social contest rolls."""

    def test_persuasion_contest(self):
        npc = _make_npc(name=_MERCHANT, attributes={_PERSUASION_SKILL: 6})
        contest_info = {"type": "persuasion", "target": _MERCHANT}
        text, roll = build_contested_action(
            "convince the merchant to lower prices",
            npc,
            contest_info=contest_info,
            _rng=random.Random(_RNG_SEED),
        )
        assert roll is not None
        assert roll.contest_type == ContestType.PERSUASION
        assert roll.target_bonus == 6
        assert roll.actor_bonus == 0
        assert _DICE_MARKER in text

    def test_deception_contest(self):
        npc = _make_npc(attributes={_DECEPTION_SKILL: 4})
        contest_info = {"type": "deception", "target": _GUARD}
        text, roll = build_contested_action(
            "lie about my identity",
            npc,
            contest_info=contest_info,
            _rng=random.Random(42),
        )
        assert roll is not None
        assert roll.contest_type == ContestType.DECEPTION

    def test_intimidation_contest(self):
        npc = _make_npc(attributes={_INTIMIDATION_SKILL: 3})
        contest_info = {"type": "intimidation", "target": _GUARD}
        text, roll = build_contested_action(
            "threaten the guard",
            npc,
            contest_info=contest_info,
            _rng=random.Random(42),
        )
        assert roll is not None
        assert roll.contest_type == ContestType.INTIMIDATION

    def test_stealth_contest(self):
        npc = _make_npc(attributes={_PERCEPTION_SKILL: 7})
        contest_info = {"type": "stealth", "target": _GUARD}
        text, roll = build_contested_action(
            "sneak past the guard",
            npc,
            contest_info=contest_info,
            _rng=random.Random(42),
        )
        assert roll is not None
        assert roll.contest_type == ContestType.STEALTH
        assert roll.target_bonus == 7

    def test_no_contest_info_no_roll(self):
        npc = _make_npc()
        text, roll = build_contested_action("talk to guard", npc, contest_info=None)
        assert roll is None
        assert text == "talk to guard"

    def test_contest_info_overrides_non_aggressive(self):
        """Contest info triggers a roll even when is_aggressive is False."""
        npc = _make_npc(attributes={_PERSUASION_SKILL: 5})
        contest_info = {"type": "persuasion", "target": _GUARD}
        text, roll = build_contested_action(
            "convince the guard",
            npc,
            is_aggressive=False,
            contest_info=contest_info,
            _rng=random.Random(42),
        )
        assert roll is not None
        assert roll.contest_type == ContestType.PERSUASION

    def test_aggressive_takes_priority_over_contest_info(self):
        """When both is_aggressive and contest_info set, combat wins."""
        npc = _make_npc(attributes={_COMBAT_SKILL: 5, _PERSUASION_SKILL: 8})
        contest_info = {"type": "persuasion", "target": _GUARD}
        text, roll = build_contested_action(
            "attack while talking",
            npc,
            is_aggressive=True,
            contest_info=contest_info,
            _rng=random.Random(42),
        )
        assert roll is not None
        assert roll.contest_type == ContestType.COMBAT


class TestBuildContestedActionDefaultSkill:
    """NPCs without explicit skill attributes default to 0."""

    def test_missing_skill_defaults_to_zero(self):
        npc = _make_npc(attributes={})
        contest_info = {"type": "persuasion", "target": _GUARD}
        _, roll = build_contested_action(
            "persuade",
            npc,
            contest_info=contest_info,
            _rng=random.Random(42),
        )
        assert roll is not None
        assert roll.target_bonus == 0
