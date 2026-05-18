"""Tests for cast.player_context.PlayerUtterance — literary player rendering."""

from __future__ import annotations

import allure

from cast.player_context import PlayerUtterance

pytestmark = [
    allure.epic("NPC short-term memory"),
    allure.feature("Player utterance rendering"),
]


_DEFAULT_APPEARANCE = "unremarkable"
_REAL_APPEARANCE = "190 cm Slav in dark furs"


@allure.story("Verb mapping")
@allure.title("TALK renders as a quoted speech sentence with appearance descriptor")
def test_talk_renders_as_speech_with_appearance() -> None:
    rendered = PlayerUtterance(
        appearance=_REAL_APPEARANCE,
        action_type="TALK",
        text="Hello, bro.",
    ).render()
    assert rendered == 'The 190 cm Slav in dark furs says: "Hello, bro."'


@allure.story("Verb mapping")
@allure.title("ATTACK renders as a non-quoted action sentence")
def test_attack_renders_as_action() -> None:
    rendered = PlayerUtterance(
        appearance=_REAL_APPEARANCE,
        action_type="ATTACK",
        text="lunges with a dagger",
    ).render()
    assert rendered == "The 190 cm Slav in dark furs attacks: lunges with a dagger"


@allure.story("Verb mapping")
@allure.title("INTIMIDATE / PERSUADE / DECEIVE quote the text as direct speech")
def test_speech_verbs_quote_text() -> None:
    intimidate = PlayerUtterance(_REAL_APPEARANCE, "INTIMIDATE", "do as I say").render()
    persuade = PlayerUtterance(_REAL_APPEARANCE, "PERSUADE", "trust me").render()
    deceive = PlayerUtterance(_REAL_APPEARANCE, "DECEIVE", "I am the king").render()
    assert intimidate == 'The 190 cm Slav in dark furs snarls: "do as I say"'
    assert persuade == 'The 190 cm Slav in dark furs urges: "trust me"'
    assert deceive == 'The 190 cm Slav in dark furs claims: "I am the king"'


@allure.story("Verb mapping")
@allure.title("Movement / exploration verbs render as actions, not speech")
def test_movement_verbs_render_as_actions() -> None:
    move = PlayerUtterance(_REAL_APPEARANCE, "MOVE", "heads to the gate").render()
    explore = PlayerUtterance(_REAL_APPEARANCE, "EXPLORE", "scans the stalls").render()
    look = PlayerUtterance(_REAL_APPEARANCE, "LOOK", "studies the statue").render()
    stealth = PlayerUtterance(_REAL_APPEARANCE, "STEALTH", "skirts the columns").render()
    assert move == "The 190 cm Slav in dark furs moves, doing: heads to the gate"
    assert explore == "The 190 cm Slav in dark furs looks around, doing: scans the stalls"
    assert look == "The 190 cm Slav in dark furs looks around, doing: studies the statue"
    assert stealth == "The 190 cm Slav in dark furs slips through, doing: skirts the columns"


@allure.story("Verb mapping")
@allure.title("Unknown action_type falls back to the generic 'does' verb")
def test_unknown_action_type_uses_default_verb() -> None:
    rendered = PlayerUtterance(_REAL_APPEARANCE, "BANANA", "trips").render()
    assert rendered == "The 190 cm Slav in dark furs does: trips"


@allure.story("Verb mapping")
@allure.title("action_type is matched case-insensitively")
def test_action_type_matched_case_insensitively() -> None:
    rendered = PlayerUtterance(_REAL_APPEARANCE, "talk", "Hi").render()
    assert rendered == 'The 190 cm Slav in dark furs says: "Hi"'


@allure.story("Descriptor drop")
@allure.title("Placeholder appearance drops the 'The <descriptor>' prefix and uses 'Player' instead")
def test_unremarkable_appearance_drops_descriptor() -> None:
    rendered = PlayerUtterance(
        appearance=_DEFAULT_APPEARANCE,
        action_type="TALK",
        text="Hello.",
    ).render()
    assert rendered == 'Player says: "Hello."'


@allure.story("Descriptor drop")
@allure.title("Empty appearance also falls back to the bare 'Player <verb>: ...' form")
def test_empty_appearance_drops_descriptor() -> None:
    rendered = PlayerUtterance(appearance="", action_type="MOVE", text="walks east").render()
    assert rendered == "Player moves, doing: walks east"
