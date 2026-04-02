"""Tests for game-related models: GameState, PlayerState, SceneNPC."""

from __future__ import annotations

import dataclasses

from models.game_state import GameState, PlayerState
from models.scene import SceneNPC

_GUARD = "guard"

_MORNING_CLOCK = 8.0
_AFTERNOON_HOURS = 13
_EVENING_HOURS = 19
_PAST_MIDNIGHT_HOURS = 25
_ACCUMULATED_CLOCK = 12.0
_HALF_DAY_HOURS = 6
_NIGHT_HOURS = 3


class TestGameStateFields:
    """Tests for GameState dataclass fields and initial values."""

    def test_has_own_dataclass_fields(self):
        field_names = {dc_field.name for dc_field in dataclasses.fields(GameState)}
        assert "turn_count" in field_names
        assert "game_clock" in field_names
        assert "conversation_log" in field_names

    def test_initial_values(self, game_state):
        assert game_state.turn_count == 0
        assert game_state.scene_number == 0
        assert game_state.game_clock == float(0)
        assert game_state.game_time == "morning"
        assert game_state.npcs == {}

    def test_initial_collections(self, game_state):
        assert game_state.locations == {}
        assert game_state.scene_conversation_log == []


class TestGameStateClockAdvance:
    """Tests for GameState.advance_clock time-of-day transitions."""

    def test_advance_clock_morning(self, game_state):
        game_state.advance_clock(_MORNING_CLOCK)
        assert game_state.game_clock == _MORNING_CLOCK
        assert game_state.game_time == "morning"

    def test_advance_clock_afternoon(self, game_state):
        game_state.advance_clock(_AFTERNOON_HOURS)
        assert game_state.game_time == "afternoon"

    def test_advance_clock_evening(self, game_state):
        game_state.advance_clock(_EVENING_HOURS)
        assert game_state.game_time == "evening"

    def test_advance_clock_night(self, game_state):
        game_state.advance_clock(_NIGHT_HOURS)
        assert game_state.game_time == "night"

    def test_advance_clock_wraps_around_midnight(self, game_state):
        game_state.advance_clock(_PAST_MIDNIGHT_HOURS)
        assert game_state.game_time == "night"

    def test_advance_clock_accumulates(self, game_state):
        game_state.advance_clock(_HALF_DAY_HOURS)
        game_state.advance_clock(_HALF_DAY_HOURS)
        assert game_state.game_clock == _ACCUMULATED_CLOCK


class TestPlayerState:
    def test_has_own_dataclass_fields(self):
        field_names = {dc_field.name for dc_field in dataclasses.fields(PlayerState)}
        assert "name" in field_names
        assert "location_id" in field_names
        assert "inventory" in field_names

    def test_defaults(self):
        ps = PlayerState()
        assert ps.name == "Player"
        assert ps.inventory == []
        assert ps.location_id is None

    def test_custom_name(self):
        ps = PlayerState(name="Maximus")
        assert ps.name == "Maximus"


class TestSceneNPCInit:
    """Tests for SceneNPC initialization and need_init behavior."""

    def test_need_init_true_by_default(self):
        snpc = SceneNPC(role=_GUARD)
        assert snpc.need_init is True
        assert snpc.uuid is None

    def test_need_init_false_after_uuid_set(self):
        snpc = SceneNPC(role=_GUARD)
        snpc.uuid = "some-uuid-1234"
        assert snpc.need_init is False

    def test_need_init_false_with_uuid_arg(self):
        snpc = SceneNPC(role="merchant", uuid="abc-123")
        assert snpc.need_init is False
        assert snpc.uuid == "abc-123"

    def test_repr(self):
        snpc = SceneNPC(role=_GUARD)
        assert "uninit" in repr(snpc)
        snpc.uuid = "abc"
        assert "abc" in repr(snpc)


class TestSceneNPCSerialization:
    """Tests for SceneNPC to_dict/from_dict round-tripping."""

    def test_to_dict(self):
        snpc = SceneNPC(role="beggar", uuid="uuid-42")
        assert snpc.to_dict() == {"role": "beggar", "uuid": "uuid-42"}

    def test_to_dict_uninitialised(self):
        snpc = SceneNPC(role=_GUARD)
        assert snpc.to_dict() == {"role": "guard", "uuid": None}

    def test_from_dict_roundtrip(self):
        original = SceneNPC(role="scribe", uuid="uuid-99")
        restored = SceneNPC.from_dict(original.to_dict())
        assert restored.role == "scribe"
        assert restored.uuid == "uuid-99"
        assert restored.need_init is False

    def test_from_dict_without_uuid(self):
        restored = SceneNPC.from_dict({"role": "merchant"})
        assert restored.role == "merchant"
        assert restored.need_init is True
