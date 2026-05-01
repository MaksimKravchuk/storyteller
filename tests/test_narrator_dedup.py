"""Direct unit tests for ``cast.narrator_dedup``.

The ``TestNarratorDedup`` class in :mod:`tests.test_narrator_branches`
exercises dedup through the full ``Narrator.act()`` pipeline, but the
``says``/``meanwhile`` labels render only ``npc_name`` + ``response``
or ``action`` — neither ``contest_roll`` (on ``DialogueEntry``) nor
``action_type`` (on ``NPCTurnEntry``) is observable through that
harness. These tests pin the merge contract directly on the helpers
so a future refactor cannot silently drop either field.
"""

from __future__ import annotations

import allure
import pytest

import uuid

from cast.narrator_dedup import dedup_dialogue, dedup_npc_turns
from cast.schemas.turn_outputs import DialogueEntry, NPCTurnEntry

# Static UUIDs so the dedup tests can pin two distinct NPCs as separate
# entities (the dedup helpers key on ``npc_uuid``, which production
# always sets to a real ``uuid4`` string from :class:`models.base_model.BaseModel`).
_IVAN_UUID = str(uuid.uuid4())
_BORIS_UUID = str(uuid.uuid4())
_FROL_UUID = str(uuid.uuid4())
_PETR_UUID = str(uuid.uuid4())


@allure.epic("Narrative Delivery")
@allure.feature("Narrator dedup")
class TestDedupDialogue:
    @allure.story("Dedup dialogue")
    @allure.title("Empty input returns an empty list")
    def test_empty_input(self):
        assert dedup_dialogue([]) == []

    @allure.story("Dedup dialogue")
    @allure.title("Single entry passes through unchanged")
    def test_single_entry_passthrough(self):
        entry = DialogueEntry(npc_name="Ivan", response="Halt!", contest_roll="2d6=9")
        result = dedup_dialogue([entry])
        assert result == [entry]

    @allure.story("Dedup dialogue")
    @allure.title("Exact-duplicate responses for one NPC collapse to a single entry")
    def test_exact_duplicates_collapse(self):
        entries = [
            DialogueEntry(npc_name="Ivan", response="Halt!"),
            DialogueEntry(npc_name="Ivan", response="Halt!"),
        ]
        result = dedup_dialogue(entries)
        assert len(result) == 1
        assert result[0].response == "Halt!"

    @allure.story("Dedup dialogue")
    @allure.title("Distinct responses for one NPC merge into one entry joined by ' / '")
    def test_distinct_responses_merge_with_literal_separator(self):
        entries = [
            DialogueEntry(npc_name="Ivan", response="Halt!"),
            DialogueEntry(npc_name="Ivan", response="Who goes there?"),
        ]
        result = dedup_dialogue(entries)
        assert len(result) == 1
        assert result[0].response == "Halt! / Who goes there?"

    @allure.story("Dedup dialogue")
    @allure.title("contest_roll is preserved when only the first entry carries one")
    def test_contest_roll_first_wins_when_second_is_none(self):
        entries = [
            DialogueEntry(npc_name="Ivan", response="Halt!", contest_roll="2d6=9"),
            DialogueEntry(npc_name="Ivan", response="Who goes there?"),
        ]
        result = dedup_dialogue(entries)
        assert result[0].contest_roll == "2d6=9"

    @allure.story("Dedup dialogue")
    @allure.title("contest_roll falls back to the incoming entry when the first is None")
    def test_contest_roll_falls_back_to_incoming_when_first_is_none(self):
        entries = [
            DialogueEntry(npc_name="Ivan", response="Halt!"),
            DialogueEntry(npc_name="Ivan", response="Who goes there?", contest_roll="2d6=11"),
        ]
        result = dedup_dialogue(entries)
        assert result[0].contest_roll == "2d6=11"

    @allure.story("Dedup dialogue")
    @allure.title("When both entries carry a contest_roll, the first-seen wins")
    def test_contest_roll_both_present_first_wins(self):
        entries = [
            DialogueEntry(npc_name="Ivan", response="Halt!", contest_roll="2d6=9"),
            DialogueEntry(npc_name="Ivan", response="Who goes there?", contest_roll="2d6=11"),
        ]
        result = dedup_dialogue(entries)
        assert result[0].contest_roll == "2d6=9"

    @allure.story("Dedup dialogue")
    @allure.title("When both entries carry no contest_roll, the merged entry also has None")
    def test_contest_roll_both_none(self):
        entries = [
            DialogueEntry(npc_name="Ivan", response="Halt!"),
            DialogueEntry(npc_name="Ivan", response="Who goes there?"),
        ]
        result = dedup_dialogue(entries)
        assert result[0].contest_roll is None

    @allure.story("Dedup dialogue")
    @allure.title("Interleaved same-NPC entries merge without disturbing other NPCs' order")
    def test_interleaved_preserves_first_appearance_order(self):
        entries = [
            DialogueEntry(npc_uuid=_IVAN_UUID, npc_name="Ivan", response="Halt!"),
            DialogueEntry(npc_uuid=_BORIS_UUID, npc_name="Boris", response="Who is it?"),
            DialogueEntry(npc_uuid=_IVAN_UUID, npc_name="Ivan", response="State your business!"),
        ]
        result = dedup_dialogue(entries)
        assert [entry.npc_name for entry in result] == ["Ivan", "Boris"]
        assert result[0].response == "Halt! / State your business!"
        assert result[1].response == "Who is it?"

    @allure.story("Dedup dialogue")
    @allure.title("Dedup is per-NPC: one NPC's duplicates do not affect another NPC's distinct lines")
    def test_mixed_duplicates_and_distinct_across_npcs(self):
        entries = [
            DialogueEntry(npc_uuid=_IVAN_UUID, npc_name="Ivan", response="Halt!"),
            DialogueEntry(npc_uuid=_BORIS_UUID, npc_name="Boris", response="Who?"),
            DialogueEntry(npc_uuid=_IVAN_UUID, npc_name="Ivan", response="Halt!"),
            DialogueEntry(npc_uuid=_BORIS_UUID, npc_name="Boris", response="Show yourself!"),
        ]
        result = dedup_dialogue(entries)
        ivan = next(entry for entry in result if entry.npc_name == "Ivan")
        boris = next(entry for entry in result if entry.npc_name == "Boris")
        assert ivan.response == "Halt!"
        assert boris.response == "Who? / Show yourself!"


@allure.epic("Narrative Delivery")
@allure.feature("Narrator dedup")
class TestDedupNPCTurns:
    @allure.story("Dedup npc_turns")
    @allure.title("Empty input returns an empty list")
    def test_empty_input(self):
        assert dedup_npc_turns([]) == []

    @allure.story("Dedup npc_turns")
    @allure.title("Exact-duplicate actions for one NPC collapse to a single entry")
    def test_exact_duplicates_collapse(self):
        entries = [
            NPCTurnEntry(npc_name="Frol", action="draws his sword", action_type="COMBAT"),
            NPCTurnEntry(npc_name="Frol", action="draws his sword", action_type="COMBAT"),
        ]
        result = dedup_npc_turns(entries)
        assert len(result) == 1
        assert result[0].action == "draws his sword"

    @allure.story("Dedup npc_turns")
    @allure.title("Distinct actions for one NPC merge into one entry joined by ' / '")
    def test_distinct_actions_merge_with_literal_separator(self):
        entries = [
            NPCTurnEntry(npc_name="Frol", action="draws his sword", action_type="COMBAT"),
            NPCTurnEntry(npc_name="Frol", action="shouts for the guard", action_type="COMBAT"),
        ]
        result = dedup_npc_turns(entries)
        assert len(result) == 1
        assert result[0].action == "draws his sword / shouts for the guard"

    @allure.story("Dedup npc_turns")
    @allure.title("action_type is preserved from the first-seen entry when two entries merge")
    def test_action_type_first_wins_on_merge(self):
        entries = [
            NPCTurnEntry(npc_name="Frol", action="draws his sword", action_type="COMBAT"),
            NPCTurnEntry(npc_name="Frol", action="ducks behind a barrel", action_type="IDLE"),
        ]
        result = dedup_npc_turns(entries)
        assert result[0].action_type == "COMBAT"

    @allure.story("Dedup npc_turns")
    @allure.title("Interleaved same-NPC turns merge without disturbing other NPCs' order")
    def test_interleaved_preserves_first_appearance_order(self):
        entries = [
            NPCTurnEntry(npc_uuid=_FROL_UUID, npc_name="Frol", action="draws his sword", action_type="COMBAT"),
            NPCTurnEntry(npc_uuid=_PETR_UUID, npc_name="Petr", action="backs away", action_type="FLEE"),
            NPCTurnEntry(npc_uuid=_FROL_UUID, npc_name="Frol", action="advances", action_type="COMBAT"),
        ]
        result = dedup_npc_turns(entries)
        assert [entry.npc_name for entry in result] == ["Frol", "Petr"]
        assert result[0].action == "draws his sword / advances"
        assert result[1].action == "backs away"


@allure.epic("Narrative Delivery")
@allure.feature("Narrator dedup")
class TestDedupReturnType:
    """Pydantic round-trip: ``dedup_*`` must return the same model types it
    accepts so callers (e.g. narrator labels that format ``entry.response``)
    don't have to re-parse.
    """

    @allure.story("Return type")
    @allure.title("dedup_dialogue returns DialogueEntry instances")
    def test_dedup_dialogue_returns_dialogue_entries(self):
        result = dedup_dialogue([DialogueEntry(npc_name="Ivan", response="Halt!")])
        assert all(isinstance(entry, DialogueEntry) for entry in result)

    @allure.story("Return type")
    @allure.title("dedup_npc_turns returns NPCTurnEntry instances")
    def test_dedup_npc_turns_returns_npc_turn_entries(self):
        result = dedup_npc_turns([NPCTurnEntry(npc_name="Frol", action="waits", action_type="IDLE")])
        assert all(isinstance(entry, NPCTurnEntry) for entry in result)


@allure.epic("Narrative Delivery")
@allure.feature("Narrator dedup")
class TestRussianPromptFaithfulnessRules:
    """Guard against EN/RU drift: the Russian role section must carry the
    same faithful-compression constraints as the English one. Without this
    pin, a future rule added to English only would silently degrade the
    Russian narrator.
    """

    @pytest.mark.parametrize(
        "phrase",
        [
            "Правила достоверности",
            "не сериализуй",
            "Лимит длины",
        ],
    )
    @allure.story("Localization")
    @allure.title("Russian narrator role section contains faithful-compression phrase: {phrase}")
    def test_russian_role_contains_faithfulness_phrase(self, phrase: str):
        from prompts.narrator_prompts_ru import NARRATOR_SYSTEM_RU

        rendered = NARRATOR_SYSTEM_RU.render(
            setting_name="Тест",
            time_period="сейчас",
            time_of_day="утро",
            language="Russian",
        )
        assert phrase in rendered
