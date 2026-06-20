"""Unit tests for cast.hostility — mechanical mood escalation."""

from __future__ import annotations

import allure
import pytest

from cast import dice, hostility
from models.npc_card import NPCCard


@pytest.fixture
def guard() -> NPCCard:
    return NPCCard(
        name="Иван",
        occupation="guard",
        speech_style="грубо-деловито",
        current_mood="neutral",
    )


@allure.epic("NPC behavior")
@allure.feature("Hostility escalation")
class TestMoodFloor:
    @allure.story("Level mapping")
    @allure.title("mood_floor returns None for hostility 0 and maps every non-zero level to a known mood")
    @pytest.mark.parametrize(
        ("level", "expected"),
        [
            (0, None),
            (1, "irritated"),
            (2, "irritated"),
            (3, "threatened"),
            (4, "threatened"),
            (5, "angry"),
            (6, "angry"),
            (7, "hostile"),
            (8, "hostile"),
            (9, "enraged"),
            (10, "enraged"),
        ],
    )
    def test_mood_floor_mapping(self, level, expected):
        assert hostility.mood_floor(level) == expected

    @allure.story("Retaliation calibration")
    @allure.title("Every non-zero mood_floor output has an AGGRESSION_THRESHOLDS entry so retaliation can roll")
    def test_floor_moods_are_aggression_eligible(self):
        for level in range(1, 11):
            mood = hostility.mood_floor(level)
            assert mood is not None
            assert mood in dice.AGGRESSION_THRESHOLDS


@allure.epic("NPC behavior")
@allure.feature("Hostility escalation")
class TestBumpHostility:
    @allure.story("Counter increments")
    @allure.title("bump_hostility increments level by severity weight and caps at 10")
    def test_low_severity_bumps_by_one(self, guard):
        hostility.bump_hostility(guard, turn=1, player_action="shoved", severity=hostility.SEVERITY_LOW)
        assert guard.hostility_level == 1

    @allure.story("Counter increments")
    @allure.title("High severity bumps by two")
    def test_high_severity_bumps_by_two(self, guard):
        hostility.bump_hostility(guard, turn=1, player_action="punched", severity=hostility.SEVERITY_HIGH)
        assert guard.hostility_level == 2

    @allure.story("Counter cap")
    @allure.title("hostility_level is capped at 10 even under sustained assault")
    def test_level_cap(self, guard):
        for turn in range(12):
            hostility.bump_hostility(guard, turn=turn, player_action="hit", severity=hostility.SEVERITY_HIGH)
        assert guard.hostility_level == 10

    @allure.story("Unknown severity fallback")
    @allure.title("Unknown severity strings fall back to the low-severity bump so the counter still moves")
    def test_unknown_severity_falls_back(self, guard):
        hostility.bump_hostility(guard, turn=1, player_action="poked", severity="weird")
        assert guard.hostility_level == 1

    @allure.story("History FIFO")
    @allure.title("recent_hostile_actions is capped at 3 entries, newest last")
    def test_history_fifo_cap(self, guard):
        for turn in range(5):
            hostility.bump_hostility(
                guard,
                turn=turn,
                player_action="attack {0}".format(turn),
                severity=hostility.SEVERITY_LOW,
            )
        assert len(guard.recent_hostile_actions) == 3
        assert guard.recent_hostile_actions[0]["turn"] == "2"
        assert guard.recent_hostile_actions[-1]["turn"] == "4"

    @allure.story("Mood floor application")
    @allure.title("bump_hostility raises current_mood to the computed floor when level crosses a threshold")
    def test_mood_raised_to_floor(self, guard):
        hostility.bump_hostility(guard, turn=1, player_action="punch", severity=hostility.SEVERITY_HIGH)
        hostility.bump_hostility(guard, turn=2, player_action="punch", severity=hostility.SEVERITY_HIGH)
        # level=4 → floor "threatened"
        assert guard.current_mood == "threatened"

    @allure.story("Mood floor application")
    @allure.title("bump_hostility does not downgrade a stronger mood the LLM already emitted")
    def test_stronger_mood_is_preserved(self, guard):
        guard.current_mood = "enraged"
        hostility.bump_hostility(guard, turn=1, player_action="punch", severity=hostility.SEVERITY_LOW)
        # level=1 → floor "irritated", but enraged > irritated
        assert guard.current_mood == "enraged"

    @allure.story("Mood floor application")
    @allure.title("bump_hostility overrides LLM-invented moods with a valid floor so retaliation can roll")
    def test_unknown_mood_is_overridden(self, guard):
        guard.current_mood = "stoic"
        hostility.bump_hostility(guard, turn=1, player_action="punch", severity=hostility.SEVERITY_HIGH)
        hostility.bump_hostility(guard, turn=2, player_action="punch", severity=hostility.SEVERITY_HIGH)
        assert guard.current_mood == "threatened"


@allure.epic("NPC behavior")
@allure.feature("Hostility escalation")
class TestApplyLLMMoodUpdate:
    @allure.story("Mood-update guard")
    @allure.title("LLM can freely pick any mood when the NPC's hostility_level is zero")
    def test_peaceful_npc_accepts_any_mood(self, guard):
        hostility.apply_llm_mood_update(guard, "worried")
        assert guard.current_mood == "worried"

    @allure.story("Mood-update guard")
    @allure.title("Hostile NPC's mechanical floor blocks an LLM downgrade to a peaceful mood")
    def test_hostile_npc_rejects_downgrade(self, guard):
        guard.hostility_level = 4  # floor = threatened
        guard.current_mood = "threatened"

        hostility.apply_llm_mood_update(guard, "calm")

        assert guard.current_mood == "threatened"

    @allure.story("Mood-update guard")
    @allure.title("LLM can still escalate past the floor — hostile NPC may become furious mid-dialogue")
    def test_hostile_npc_accepts_escalation(self, guard):
        guard.hostility_level = 4  # floor = threatened
        guard.current_mood = "threatened"

        hostility.apply_llm_mood_update(guard, "furious")

        assert guard.current_mood == "furious"

    @allure.story("Mood-update guard")
    @allure.title("LLM may shift sideways at or above the floor — threatened → hostile is allowed")
    def test_hostile_npc_accepts_sideways_at_or_above_floor(self, guard):
        guard.hostility_level = 3  # floor = threatened
        guard.current_mood = "threatened"

        hostility.apply_llm_mood_update(guard, "hostile")

        assert guard.current_mood == "hostile"

    @allure.story("Emotional-floor guard")
    @allure.title("An emotional floor blocks an LLM downgrade even at hostility 0")
    def test_emotional_floor_blocks_downgrade_at_zero_hostility(self, guard):
        guard.hostility_level = 0  # no mechanical floor
        guard.current_mood = "hostile"
        guard.emotional_mood_floor = "hostile"

        hostility.apply_llm_mood_update(guard, "calm")

        assert guard.current_mood == "hostile"

    @allure.story("Emotional-floor guard")
    @allure.title("An emotional floor still lets the LLM escalate above it")
    def test_emotional_floor_allows_escalation(self, guard):
        guard.emotional_mood_floor = "angry"

        hostility.apply_llm_mood_update(guard, "enraged")

        assert guard.current_mood == "enraged"

    @allure.story("Emotional-floor guard")
    @allure.title("The effective floor is the stronger of the mechanical and emotional floors")
    def test_effective_floor_takes_stronger_of_the_two(self, guard):
        guard.hostility_level = 1  # mechanical floor = irritated
        guard.emotional_mood_floor = "hostile"  # stronger
        guard.current_mood = "hostile"

        # "angry" outranks the mechanical floor but not the emotional one.
        hostility.apply_llm_mood_update(guard, "angry")

        assert guard.current_mood == "hostile"


@allure.epic("NPC behavior")
@allure.feature("Hostility escalation")
class TestFormatSummary:
    @allure.story("Prompt rendering")
    @allure.title("format_hostile_actions_summary yields an empty string for empty input")
    def test_empty_summary(self):
        assert hostility.format_hostile_actions_summary([]) == ""

    @allure.story("Prompt rendering")
    @allure.title("format_hostile_actions_summary renders a bulleted list with turn, severity, and action")
    def test_summary_rendering(self):
        entries = [
            {"turn": "1", "action": "shoved you", "severity": "low"},
            {"turn": "3", "action": "punched your jaw", "severity": "high"},
        ]
        rendered = hostility.format_hostile_actions_summary(entries)
        assert "Turn 1 (low): shoved you" in rendered
        assert "Turn 3 (high): punched your jaw" in rendered
        assert rendered.count("\n") == 1
