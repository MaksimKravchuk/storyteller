"""Tests for Director core: private attributes, game state fields, and Actor._extract_mood."""

from __future__ import annotations

import dataclasses

from cast.actor import _extract_mood as _actor_extract_mood
from cast.director import DirectorCast
from tests.director_helpers import make_director, make_game_state

_HOSTILE = "hostile"


class TestDirectorPrivateAttrs:
    """Director stores deps/cast as private attrs, not public."""

    def test_no_public_game_state(self):
        director = make_director()
        assert not hasattr(director, "game_state")
        assert director._deps.game_state is not None

    def test_no_public_cast_attrs(self):
        director = make_director()
        cast_fields = [field.name for field in dataclasses.fields(DirectorCast)]
        for attr in cast_fields:
            assert not hasattr(director, attr), "Director should not have public attr {0}".format(attr)

    def test_actors_private(self):
        director = make_director()
        assert not hasattr(director, "actors")
        assert isinstance(director._actors, dict)


class TestGameStateSceneFields:
    def test_initial_scene_number(self):
        gs = make_game_state()
        assert gs.scene_number == 0

    def test_initial_scene_conversation_log(self):
        gs = make_game_state()
        assert not gs.scene_conversation_log


class TestExtractMood:
    def test_no_mood_tag(self):
        text, mood = _actor_extract_mood("*draws his sword* — Stand back!")
        assert text == "*draws his sword* — Stand back!"
        assert mood is None

    def test_mood_tag_at_end(self):
        text, mood = _actor_extract_mood(f"*lunges at you with a spear*\n[MOOD: {_HOSTILE}]")
        assert text == "*lunges at you with a spear*"
        assert mood == _HOSTILE

    def test_mood_tag_uppercase_normalised(self):
        text, mood = _actor_extract_mood("Back off!\n[MOOD: ENRAGED]")
        assert mood == "enraged"

    def test_mood_tag_with_extra_space_before_word(self):
        text, mood = _actor_extract_mood("Help!\n[MOOD:  terrified]")
        assert mood == "terrified"

    def test_mood_tag_not_at_end_is_ignored(self):
        text, mood = _actor_extract_mood(f"[MOOD: {_HOSTILE}]\nI will destroy you!")
        assert mood is None
        assert f"[MOOD: {_HOSTILE}]" in text

    def test_empty_string(self):
        text, mood = _actor_extract_mood("")
        assert text == ""
        assert mood is None
