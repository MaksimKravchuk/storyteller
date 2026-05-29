"""Tests for the dice serialization helpers and the NPC-contest turn event.

The ``*_to_dict`` helpers feed the structured turn-events log, and
``record_npc_contest_event`` is the producer that emits a ``dice_contest``
entry. Both are exercised indirectly by the cast modules but had no direct
assertions on the produced shape, so mutation testing could flip dict keys and
field sources undetected. These tests assert the exact payloads.
"""

from __future__ import annotations

import types

import allure

from cast.dice import (
    AggressionRoll,
    ContestOutcome,
    ContestRoll,
    ContestType,
    aggression_roll_to_dict,
    contest_roll_to_dict,
    record_npc_contest_event,
)
from llm.call_logger import current_session_id
from llm.turn_event_logger import get_and_clear_events, reset_events
from tests._uuid_helpers import make_uuid


@allure.epic("Combat & Action Resolution")
@allure.feature("Contest dice")
class TestContestSerialization:
    @allure.story("Serialization")
    @allure.title("contest_roll_to_dict maps every ContestRoll field to its JSON key")
    def test_contest_roll_to_dict(self):
        # Distinct values per field so a key/value swap (e.g. actor<->target) is caught.
        roll = ContestRoll(
            contest_type=ContestType.PERSUASION,
            outcome=ContestOutcome.ACTOR_SUCCEEDS,
            actor_roll=14,
            target_roll=10,
            actor_bonus=3,
            target_bonus=1,
        )

        assert contest_roll_to_dict(roll) == {
            "contest_type": "persuasion",
            "outcome": "actor_succeeds",
            "actor_roll": 14,
            "target_roll": 10,
            "actor_bonus": 3,
            "target_bonus": 1,
            "description": roll.description,
        }

    @allure.story("Serialization")
    @allure.title("aggression_roll_to_dict maps every AggressionRoll field to its JSON key")
    def test_aggression_roll_to_dict(self):
        roll = AggressionRoll(will_attack=True, roll=17, threshold=8, mood="angry")

        assert aggression_roll_to_dict(roll) == {
            "will_attack": True,
            "roll": 17,
            "threshold": 8,
            "mood": "angry",
        }


@allure.epic("Combat & Action Resolution")
@allure.feature("Contest dice")
class TestRecordNpcContestEvent:
    @allure.story("Turn events")
    @allure.title("record_npc_contest_event emits a dice_contest event with roll + actor fields")
    def test_records_full_payload(self):
        current_session_id.set("sess-contest")
        reset_events()
        npc_uuid = make_uuid("borin")
        npc = types.SimpleNamespace(name="Borin", uuid=npc_uuid)
        roll = ContestRoll(
            contest_type=ContestType.INTIMIDATION,
            outcome=ContestOutcome.ACTOR_DOMINATES,
            actor_roll=19,
            target_roll=4,
            actor_bonus=2,
            target_bonus=0,
        )

        record_npc_contest_event(roll, npc, action_type="INTIMIDATE", target_name="the guard")

        events = get_and_clear_events()
        assert len(events) == 1
        event = events[0]
        assert event["event_type"] == "dice_contest"
        assert event["npc_id"] == str(npc_uuid)
        assert event["payload"] == {
            **contest_roll_to_dict(roll),
            "actor_npc_name": "Borin",
            "action_type": "INTIMIDATE",
            "target_name": "the guard",
        }
