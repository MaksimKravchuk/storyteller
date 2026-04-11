"""Tests for Director core: private attributes and game state scene fields."""

from __future__ import annotations

import dataclasses

import allure

from cast.director import DirectorCast
from tests.director_helpers import make_director, make_game_state


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
