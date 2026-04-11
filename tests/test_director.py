"""Tests for Director core: private attributes, game state fields, and Actor._extract_mood."""

from __future__ import annotations

import dataclasses

import allure

from cast.actor import _extract_mood as _actor_extract_mood
from cast.director import DirectorCast
from tests.director_helpers import make_director, make_game_state

_HOSTILE = "hostile"


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Director orchestration")
class TestDirectorPrivateAttrs:
    """Director stores deps/cast as private attrs, not public."""

    @allure.story("Private attribute encapsulation")
    @allure.title(
        "Director does not expose game_state as a public attribute but keeps it on the private deps container"
    )
    def test_no_public_game_state(self):
        director = make_director()
        assert not hasattr(director, "game_state")
        assert director._deps.game_state is not None

    @allure.story("Private attribute encapsulation")
    @allure.title("None of the DirectorCast fields leak onto the Director as public attributes")
    def test_no_public_cast_attrs(self):
        director = make_director()
        cast_fields = [field.name for field in dataclasses.fields(DirectorCast)]
        for attr in cast_fields:
            assert not hasattr(director, attr), "Director should not have public attr {0}".format(attr)

    @allure.story("Private attribute encapsulation")
    @allure.title("Director keeps its actors registry as a private dict (_actors) rather than a public attribute")
    def test_actors_private(self):
        director = make_director()
        assert not hasattr(director, "actors")
        assert isinstance(director._actors, dict)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Director orchestration")
class TestGameStateSceneFields:
    @allure.story("GameState scene fields")
    @allure.title("A freshly created GameState starts with scene_number set to zero")
    def test_initial_scene_number(self):
        gs = make_game_state()
        assert gs.scene_number == 0

    @allure.story("GameState scene fields")
    @allure.title("A freshly created GameState has an empty scene_conversation_log")
    def test_initial_scene_conversation_log(self):
        gs = make_game_state()
        assert not gs.scene_conversation_log


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Director orchestration")
class TestExtractMood:
    @allure.story("Mood tag extraction")
    @allure.title("Actor mood extraction leaves text unchanged and returns no mood when there is no [MOOD:] tag")
    def test_no_mood_tag(self):
        text, mood = _actor_extract_mood("*draws his sword* — Stand back!")
        assert text == "*draws his sword* — Stand back!"
        assert mood is None

    @allure.story("Mood tag extraction")
    @allure.title("Actor mood extraction strips a trailing [MOOD: hostile] tag and returns the mood value")
    def test_mood_tag_at_end(self):
        text, mood = _actor_extract_mood(f"*lunges at you with a spear*\n[MOOD: {_HOSTILE}]")
        assert text == "*lunges at you with a spear*"
        assert mood == _HOSTILE

    @allure.story("Mood tag extraction")
    @allure.title("Actor mood extraction normalizes uppercase mood values to lowercase")
    def test_mood_tag_uppercase_normalised(self):
        text, mood = _actor_extract_mood("Back off!\n[MOOD: ENRAGED]")
        assert mood == "enraged"

    @allure.story("Mood tag extraction")
    @allure.title("Actor mood extraction tolerates extra whitespace between the [MOOD:] label and the value")
    def test_mood_tag_with_extra_space_before_word(self):
        text, mood = _actor_extract_mood("Help!\n[MOOD:  terrified]")
        assert mood == "terrified"

    @allure.story("Mood tag extraction")
    @allure.title("A [MOOD:] tag that is not at the end of the response is ignored and left in the text")
    def test_mood_tag_not_at_end_is_ignored(self):
        text, mood = _actor_extract_mood(f"[MOOD: {_HOSTILE}]\nI will destroy you!")
        assert mood is None
        assert f"[MOOD: {_HOSTILE}]" in text

    @allure.story("Mood tag extraction")
    @allure.title("Actor mood extraction handles an empty response string without error")
    def test_empty_string(self):
        text, mood = _actor_extract_mood("")
        assert text == ""
        assert mood is None
