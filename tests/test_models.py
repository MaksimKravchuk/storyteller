"""Tests for models: BaseModel, Character, NPCCard, Location, Setting, GameState, SceneNPC."""

from __future__ import annotations

import pytest

from models.base_model import BaseModel
from models.character import Character
from models.game_state import PlayerState
from models.scene import SceneNPC
from models.setting import Setting

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_UUID_LEN = 36
_DAGGER = "dagger"
_NPC_A = "npc-1"
_GUARD = "guard"
_CLOCK_MORNING = 8.0
_CLOCK_NOON = 12.0
_HOURS_MORNING = 8
_HOURS_AFTERNOON = 13
_HOURS_EVENING = 19
_HOURS_THREE_AM = 3
_HOURS_NIGHT = 25


# ---------------------------------------------------------------------------
# BaseModel
# ---------------------------------------------------------------------------


class TestBaseModel:
    def test_uuid_generated_on_init(self):
        model = BaseModel()
        assert isinstance(model.uuid, str)
        assert len(model.uuid) == _UUID_LEN  # standard UUID4 format

    def test_unique_uuids(self):
        uuids = {BaseModel().uuid for _ in range(100)}
        assert len(uuids) == 100


# ---------------------------------------------------------------------------
# Character
# ---------------------------------------------------------------------------


class TestCharacter:
    def test_defaults(self):
        char = Character(name="Livia")
        assert char.name == "Livia"
        assert char.biography == ""
        assert char.relationships == {}
        assert char.attributes == {}
        assert char.inventory == []
        assert char.personality_traits == []
        assert char.knowledge_scope == "local"

    def test_add_relationship(self):
        char = Character(name="Brutus")
        char.add_relationship("caesar-uuid", "enemy")
        assert char.relationships["caesar-uuid"] == "enemy"

    def test_update_and_get_attribute(self):
        char = Character(name="Cato")
        char.update_attribute("strength", 7)
        assert char.get_attribute("strength") == 7
        assert char.get_attribute("wisdom", default=5) == 5

    def test_inventory_add_and_remove(self):
        char = Character(name="Cassius")
        char.add_item_to_inventory(_DAGGER)
        assert _DAGGER in char.inventory
        char.remove_item_from_inventory(_DAGGER)
        assert _DAGGER not in char.inventory

    def test_remove_item_not_in_inventory_raises(self):
        char = Character(name="Cassius")
        with pytest.raises(ValueError, match=_DAGGER):
            char.remove_item_from_inventory("dagger")

    def test_talk(self):
        char = Character(name="Cicero")
        assert char.talk() == "Cicero says: Hello!"


# ---------------------------------------------------------------------------
# NPCCard
# ---------------------------------------------------------------------------


class TestNPCCard:
    def test_to_prompt_context_contains_name(self, sample_npc):
        ctx = sample_npc.to_prompt_context()
        assert "Marcus" in ctx

    def test_to_prompt_context_contains_occupation(self, sample_npc):
        ctx = sample_npc.to_prompt_context()
        assert "Soldier" in ctx

    def test_to_prompt_context_contains_traits(self, sample_npc):
        ctx = sample_npc.to_prompt_context()
        assert "brave" in ctx
        assert "loyal" in ctx

    def test_to_prompt_context_shows_inventory(self, sample_npc):
        ctx = sample_npc.to_prompt_context()
        assert "gladius" in ctx
        assert "scutum" in ctx

    def test_to_prompt_context_shows_attributes(self, sample_npc):
        ctx = sample_npc.to_prompt_context()
        assert "strength=8" in ctx

    def test_conversation_history_starts_empty(self, sample_npc):
        assert sample_npc.conversation_history == []

    def test_current_mood_default(self, sample_npc):
        assert sample_npc.current_mood == "neutral"


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------


class TestLocation:
    def test_defaults(self, sample_location):
        assert sample_location.name == "Forum Romanum"
        assert sample_location.npcs_present == []
        assert sample_location.points_of_interest == []

    def test_add_npc(self, sample_location):
        sample_location.add_npc(_NPC_A)
        assert _NPC_A in sample_location.npcs_present

    def test_add_npc_idempotent(self, sample_location):
        sample_location.add_npc(_NPC_A)
        sample_location.add_npc(_NPC_A)
        assert sample_location.npcs_present.count(_NPC_A) == 1

    def test_remove_npc(self, sample_location):
        sample_location.add_npc(_NPC_A)
        sample_location.remove_npc(_NPC_A)
        assert _NPC_A not in sample_location.npcs_present

    def test_remove_npc_not_present_is_noop(self, sample_location):
        sample_location.remove_npc("ghost")  # should not raise


# ---------------------------------------------------------------------------
# Setting
# ---------------------------------------------------------------------------


class TestSetting:
    def test_required_fields(self, simple_setting):
        assert simple_setting.name == "Ancient Rome"
        assert simple_setting.time_period == "1st century AD"
        assert simple_setting.region == "Italy"

    def test_optional_lists_default_empty(self):
        setting = Setting(name="X", time_period="Y", region="Z", summary="S")
        assert setting.key_persons == []
        assert setting.key_events == []
        assert setting.locations == []
        assert setting.traditions == []
        assert setting.technologies == []
        assert setting.raw_sources == []

    def test_key_persons_stored(self, simple_setting):
        assert simple_setting.key_persons[0]["name"] == "Augustus"

    def test_has_uuid(self, simple_setting):
        assert isinstance(simple_setting.uuid, str) and len(simple_setting.uuid) == _UUID_LEN


# ---------------------------------------------------------------------------
# GameState / PlayerState
# ---------------------------------------------------------------------------


class TestPlayerState:
    def test_defaults(self):
        ps = PlayerState()
        assert ps.name == "Player"
        assert ps.inventory == []
        assert ps.location_id is None

    def test_custom_name(self):
        ps = PlayerState(name="Maximus")
        assert ps.name == "Maximus"


class TestGameState:
    def test_initial_values(self, game_state):
        assert game_state.turn_count == 0
        assert game_state.scene_number == 0
        assert game_state.game_clock == float(0)
        assert game_state.game_time == "morning"
        assert game_state.npcs == {}
        assert game_state.locations == {}
        assert game_state.scene_conversation_log == []

    def test_advance_clock_morning(self, game_state):
        game_state.advance_clock(_HOURS_MORNING)
        assert game_state.game_clock == _CLOCK_MORNING  # noqa: WPS459
        assert game_state.game_time == "morning"

    def test_advance_clock_afternoon(self, game_state):
        game_state.advance_clock(_HOURS_AFTERNOON)
        assert game_state.game_time == "afternoon"

    def test_advance_clock_evening(self, game_state):
        game_state.advance_clock(_HOURS_EVENING)
        assert game_state.game_time == "evening"

    def test_advance_clock_night(self, game_state):
        game_state.advance_clock(_HOURS_THREE_AM)  # 3 AM
        assert game_state.game_time == "night"

    def test_advance_clock_wraps_around_midnight(self, game_state):
        game_state.advance_clock(_HOURS_NIGHT)  # 25 hours => 1 AM next day
        assert game_state.game_time == "night"

    def test_advance_clock_accumulates(self, game_state):
        game_state.advance_clock(6)
        game_state.advance_clock(6)
        assert game_state.game_clock == _CLOCK_NOON  # noqa: WPS459


# ---------------------------------------------------------------------------
# SceneNPC
# ---------------------------------------------------------------------------


class TestSceneNPC:
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

    def test_to_dict(self):
        snpc = SceneNPC(role="beggar", uuid="uuid-42")
        snpc_dict = snpc.to_dict()
        assert snpc_dict == {"role": "beggar", "uuid": "uuid-42"}

    def test_to_dict_uninitialised(self):
        snpc = SceneNPC(role=_GUARD)
        snpc_dict = snpc.to_dict()
        assert snpc_dict == {"role": "guard", "uuid": None}

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

    def test_repr(self):
        snpc = SceneNPC(role=_GUARD)
        assert "uninit" in repr(snpc)
        snpc.uuid = "abc"
        assert "abc" in repr(snpc)
