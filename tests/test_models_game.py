"""Tests for game-related models: GameState, PlayerState, SceneNPC."""

from __future__ import annotations

import dataclasses

import allure

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


@allure.epic("Memory & Persistence")
@allure.feature("GameState model")
class TestGameStateFields:
    """Tests for GameState dataclass fields and initial values."""

    @allure.story("Dataclass fields")
    @allure.title("GameState declares its own dataclass fields for turn_count, game_clock, and conversation_log")
    def test_has_own_dataclass_fields(self):
        field_names = {dc_field.name for dc_field in dataclasses.fields(GameState)}
        assert "turn_count" in field_names
        assert "game_clock" in field_names
        assert "conversation_log" in field_names

    @allure.story("Initial values")
    @allure.title("A new GameState begins at turn 0, scene 0, clock 0.0, 'morning' time, with no NPCs")
    def test_initial_values(self, game_state):
        assert game_state.turn_count == 0
        assert game_state.scene_number == 0
        assert game_state.game_clock == float(0)
        assert game_state.game_time == "morning"
        assert game_state.npcs == {}

    @allure.story("Initial values")
    @allure.title("A new GameState starts with empty locations dict and empty scene_conversation_log")
    def test_initial_collections(self, game_state):
        assert game_state.locations == {}
        assert game_state.scene_conversation_log == []


@allure.epic("Memory & Persistence")
@allure.feature("GameState model")
class TestGameStateClockAdvance:
    """Tests for GameState.advance_clock time-of-day transitions."""

    @allure.story("Clock advance")
    @allure.title("Advancing the clock to 8.0 hours places the game in the 'morning' time-of-day bucket")
    def test_advance_clock_morning(self, game_state):
        game_state.advance_clock(_MORNING_CLOCK)
        assert game_state.game_clock == _MORNING_CLOCK
        assert game_state.game_time == "morning"

    @allure.story("Clock advance")
    @allure.title("Advancing the clock past 13 hours places the game in the 'afternoon' time-of-day bucket")
    def test_advance_clock_afternoon(self, game_state):
        game_state.advance_clock(_AFTERNOON_HOURS)
        assert game_state.game_time == "afternoon"

    @allure.story("Clock advance")
    @allure.title("Advancing the clock past 19 hours places the game in the 'evening' time-of-day bucket")
    def test_advance_clock_evening(self, game_state):
        game_state.advance_clock(_EVENING_HOURS)
        assert game_state.game_time == "evening"

    @allure.story("Clock advance")
    @allure.title("Advancing the clock by 3 hours from the start places the game into 'night'")
    def test_advance_clock_night(self, game_state):
        game_state.advance_clock(_NIGHT_HOURS)
        assert game_state.game_time == "night"

    @allure.story("Clock advance")
    @allure.title("Advancing the clock beyond 24 hours wraps around midnight and resolves to 'night'")
    def test_advance_clock_wraps_around_midnight(self, game_state):
        game_state.advance_clock(_PAST_MIDNIGHT_HOURS)
        assert game_state.game_time == "night"

    @allure.story("Clock advance")
    @allure.title("Successive calls to advance_clock sum the hours rather than replacing them")
    def test_advance_clock_accumulates(self, game_state):
        game_state.advance_clock(_HALF_DAY_HOURS)
        game_state.advance_clock(_HALF_DAY_HOURS)
        assert game_state.game_clock == _ACCUMULATED_CLOCK


@allure.epic("Memory & Persistence")
@allure.feature("GameState model")
class TestPlayerState:
    @allure.story("PlayerState")
    @allure.title("PlayerState declares its own dataclass fields for name, location_id, and inventory")
    def test_has_own_dataclass_fields(self):
        field_names = {dc_field.name for dc_field in dataclasses.fields(PlayerState)}
        assert "name" in field_names
        assert "location_id" in field_names
        assert "inventory" in field_names

    @allure.story("PlayerState")
    @allure.title("A new PlayerState defaults to name 'Player', empty inventory, and no location")
    def test_defaults(self):
        ps = PlayerState()
        assert ps.name == "Player"
        assert ps.inventory == []
        assert ps.location_id is None
        assert ps.known_npcs == set()
        assert ps.player_event_log == []
        assert ps.learned_facts == set()

    @allure.story("PlayerState")
    @allure.title("PlayerState accepts a custom player name at construction time")
    def test_custom_name(self):
        ps = PlayerState(name="Maximus")
        assert ps.name == "Maximus"


@allure.epic("Memory & Persistence")
@allure.feature("GameState model")
class TestSceneNPCInit:
    """Tests for SceneNPC initialization and need_init behavior."""

    @allure.story("SceneNPC init")
    @allure.title("A SceneNPC constructed with only a role has need_init=True and no UUID yet")
    def test_need_init_true_by_default(self):
        snpc = SceneNPC(role=_GUARD)
        assert snpc.need_init is True
        assert snpc.uuid is None

    @allure.story("SceneNPC init")
    @allure.title("Setting a UUID on a SceneNPC after construction flips need_init to False")
    def test_need_init_false_after_uuid_set(self):
        snpc = SceneNPC(role=_GUARD)
        snpc.uuid = "some-uuid-1234"
        assert snpc.need_init is False

    @allure.story("SceneNPC init")
    @allure.title("Constructing a SceneNPC with an explicit UUID skips the need_init flag")
    def test_need_init_false_with_uuid_arg(self):
        snpc = SceneNPC(role="merchant", uuid="abc-123")
        assert snpc.need_init is False
        assert snpc.uuid == "abc-123"

    @allure.story("SceneNPC init")
    @allure.title("SceneNPC repr exposes role and uuid=None before init and the UUID afterwards")
    def test_repr(self):
        snpc = SceneNPC(role=_GUARD)
        assert _GUARD in repr(snpc)
        assert "None" in repr(snpc)
        snpc.uuid = "abc"
        assert "abc" in repr(snpc)


@allure.epic("Memory & Persistence")
@allure.feature("GameState model")
class TestSceneNPCSerialization:
    """Tests for SceneNPC pydantic serialization round-tripping."""

    @allure.story("SceneNPC serialization")
    @allure.title("SceneNPC.model_dump serializes role and UUID into a plain dict")
    def test_model_dump(self):
        snpc = SceneNPC(role="beggar", uuid="uuid-42")
        assert snpc.model_dump() == {"role": "beggar", "uuid": "uuid-42"}

    @allure.story("SceneNPC serialization")
    @allure.title("An uninitialized SceneNPC serializes with uuid=None")
    def test_model_dump_uninitialised(self):
        snpc = SceneNPC(role=_GUARD)
        assert snpc.model_dump() == {"role": "guard", "uuid": None}

    @allure.story("SceneNPC serialization")
    @allure.title("SceneNPC model_dump/model_validate round-trips role and UUID and preserves the initialized state")
    def test_model_validate_roundtrip(self):
        original = SceneNPC(role="scribe", uuid="uuid-99")
        restored = SceneNPC.model_validate(original.model_dump())
        assert restored.role == "scribe"
        assert restored.uuid == "uuid-99"
        assert restored.need_init is False

    @allure.story("SceneNPC serialization")
    @allure.title("SceneNPC.model_validate without a UUID produces a fresh uninitialized SceneNPC")
    def test_model_validate_without_uuid(self):
        restored = SceneNPC.model_validate({"role": "merchant"})
        assert restored.role == "merchant"
        assert restored.need_init is True
