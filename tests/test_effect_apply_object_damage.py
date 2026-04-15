"""KER-16 — EffectApplier handler for ``APPLY_OBJECT_DAMAGE``.

``APPLY_OBJECT_DAMAGE`` is the timeline-pipeline entry point for
writing into ``Location.object_states``. These tests pin the happy
path and every no-op guard so a misrouted or under-specified effect
cannot corrupt the location dict or raise.
"""

from __future__ import annotations

import allure

from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.location import Location
from models.setting import Setting
from timeline.effect_applier import EffectApplier
from timeline.event import EventEffect

_EFFECT_TYPE = "APPLY_OBJECT_DAMAGE"
_LOCATION_ID = "tavern"
_OBJECT_KEY = "shutter"
_STATE_DESC = "splintered; frame torn loose"


def _make_game_state_with_location() -> GameState:
    gs = GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=KnowledgeGraph(),
    )
    gs.locations[_LOCATION_ID] = Location(uuid=_LOCATION_ID, name="Tavern")
    return gs


@allure.epic("Game Timeline")
@allure.feature("Effect application")
class TestApplyObjectDamageEffect:
    @allure.story("Apply object damage")
    @allure.title("APPLY_OBJECT_DAMAGE writes the state description into Location.object_states under object_key")
    def test_writes_state_into_location(self):
        gs = _make_game_state_with_location()
        applier = EffectApplier(gs, KnowledgeGraph())

        effect = EventEffect(
            effect_type=_EFFECT_TYPE,
            target_id=_LOCATION_ID,
            effect_data={
                "location_id": _LOCATION_ID,
                "object_key": _OBJECT_KEY,
                "state_description": _STATE_DESC,
            },
        )
        applier.apply(effect)

        assert gs.locations[_LOCATION_ID].object_states == {_OBJECT_KEY: _STATE_DESC}

    @allure.story("Apply object damage")
    @allure.title("APPLY_OBJECT_DAMAGE overwrites the prior state when the same object_key is written twice")
    def test_overwrites_existing_entry(self):
        gs = _make_game_state_with_location()
        gs.locations[_LOCATION_ID].object_states[_OBJECT_KEY] = "cracked"
        applier = EffectApplier(gs, KnowledgeGraph())

        effect = EventEffect(
            effect_type=_EFFECT_TYPE,
            target_id=_LOCATION_ID,
            effect_data={
                "location_id": _LOCATION_ID,
                "object_key": _OBJECT_KEY,
                "state_description": _STATE_DESC,
            },
        )
        applier.apply(effect)

        assert gs.locations[_LOCATION_ID].object_states[_OBJECT_KEY] == _STATE_DESC

    @allure.story("Apply object damage")
    @allure.title("APPLY_OBJECT_DAMAGE falls back to target_id when effect_data omits location_id")
    def test_target_id_fallback_for_location(self):
        gs = _make_game_state_with_location()
        applier = EffectApplier(gs, KnowledgeGraph())

        effect = EventEffect(
            effect_type=_EFFECT_TYPE,
            target_id=_LOCATION_ID,
            effect_data={"object_key": _OBJECT_KEY, "state_description": _STATE_DESC},
        )
        applier.apply(effect)

        assert gs.locations[_LOCATION_ID].object_states == {_OBJECT_KEY: _STATE_DESC}

    @allure.story("No-op on missing target")
    @allure.title("APPLY_OBJECT_DAMAGE targeting an unknown location_id is silently ignored without raising")
    def test_noop_when_location_missing(self):
        gs = _make_game_state_with_location()
        applier = EffectApplier(gs, KnowledgeGraph())

        effect = EventEffect(
            effect_type=_EFFECT_TYPE,
            target_id="nonexistent",
            effect_data={
                "location_id": "nonexistent",
                "object_key": _OBJECT_KEY,
                "state_description": _STATE_DESC,
            },
        )
        applier.apply(effect)

        assert gs.locations[_LOCATION_ID].object_states == {}

    @allure.story("No-op on missing target")
    @allure.title("APPLY_OBJECT_DAMAGE with an empty object_key leaves the location's object_states untouched")
    def test_noop_when_object_key_empty(self):
        gs = _make_game_state_with_location()
        applier = EffectApplier(gs, KnowledgeGraph())

        effect = EventEffect(
            effect_type=_EFFECT_TYPE,
            target_id=_LOCATION_ID,
            effect_data={
                "location_id": _LOCATION_ID,
                "object_key": "",
                "state_description": _STATE_DESC,
            },
        )
        applier.apply(effect)

        assert gs.locations[_LOCATION_ID].object_states == {}

    @allure.story("No-op on missing target")
    @allure.title("APPLY_OBJECT_DAMAGE with an empty state_description leaves the location's object_states untouched")
    def test_noop_when_state_description_empty(self):
        gs = _make_game_state_with_location()
        applier = EffectApplier(gs, KnowledgeGraph())

        effect = EventEffect(
            effect_type=_EFFECT_TYPE,
            target_id=_LOCATION_ID,
            effect_data={
                "location_id": _LOCATION_ID,
                "object_key": _OBJECT_KEY,
                "state_description": "",
            },
        )
        applier.apply(effect)

        assert gs.locations[_LOCATION_ID].object_states == {}
