"""Tests for models: BaseModel, Character, NPCCard, Location, Setting, GameState."""

from __future__ import annotations

import pytest

from models.base_model import BaseModel
from models.character import Character
from models.game_state import GameState, PlayerState
from models.location import Location
from models.npc_card import NPCCard
from models.setting import Setting


# ---------------------------------------------------------------------------
# BaseModel
# ---------------------------------------------------------------------------

class TestBaseModel:
    def test_uuid_generated_on_init(self):
        m = BaseModel()
        assert isinstance(m.uuid, str)
        assert len(m.uuid) == 36  # standard UUID4 format

    def test_unique_uuids(self):
        uuids = {BaseModel().uuid for _ in range(100)}
        assert len(uuids) == 100


# ---------------------------------------------------------------------------
# Character
# ---------------------------------------------------------------------------

class TestCharacter:
    def test_defaults(self):
        c = Character(name="Livia")
        assert c.name == "Livia"
        assert c.biography == ""
        assert c.relationships == {}
        assert c.attributes == {}
        assert c.inventory == []
        assert c.personality_traits == []
        assert c.knowledge_scope == "local"

    def test_add_relationship(self):
        c = Character(name="Brutus")
        c.add_relationship("caesar-uuid", "enemy")
        assert c.relationships["caesar-uuid"] == "enemy"

    def test_update_and_get_attribute(self):
        c = Character(name="Cato")
        c.update_attribute("strength", 7)
        assert c.get_attribute("strength") == 7
        assert c.get_attribute("wisdom", default=5) == 5

    def test_inventory_add_and_remove(self):
        c = Character(name="Cassius")
        c.add_item_to_inventory("dagger")
        assert "dagger" in c.inventory
        c.remove_item_from_inventory("dagger")
        assert "dagger" not in c.inventory

    def test_remove_item_not_in_inventory_raises(self):
        c = Character(name="Cassius")
        with pytest.raises(ValueError, match="dagger"):
            c.remove_item_from_inventory("dagger")

    def test_talk(self):
        c = Character(name="Cicero")
        assert c.talk() == "Cicero says: Hello!"


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
        sample_location.add_npc("npc-1")
        assert "npc-1" in sample_location.npcs_present

    def test_add_npc_idempotent(self, sample_location):
        sample_location.add_npc("npc-1")
        sample_location.add_npc("npc-1")
        assert sample_location.npcs_present.count("npc-1") == 1

    def test_remove_npc(self, sample_location):
        sample_location.add_npc("npc-1")
        sample_location.remove_npc("npc-1")
        assert "npc-1" not in sample_location.npcs_present

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
        s = Setting(name="X", time_period="Y", region="Z", summary="S")
        assert s.key_persons == []
        assert s.key_events == []
        assert s.locations == []
        assert s.traditions == []
        assert s.technologies == []
        assert s.raw_sources == []

    def test_key_persons_stored(self, simple_setting):
        assert simple_setting.key_persons[0]["name"] == "Augustus"

    def test_has_uuid(self, simple_setting):
        assert isinstance(simple_setting.uuid, str) and len(simple_setting.uuid) == 36


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
        assert game_state.game_clock == 0.0
        assert game_state.game_time == "morning"
        assert game_state.npcs == {}
        assert game_state.locations == {}

    def test_advance_clock_morning(self, game_state):
        game_state.advance_clock(8)
        assert game_state.game_clock == 8.0
        assert game_state.game_time == "morning"

    def test_advance_clock_afternoon(self, game_state):
        game_state.advance_clock(13)
        assert game_state.game_time == "afternoon"

    def test_advance_clock_evening(self, game_state):
        game_state.advance_clock(19)
        assert game_state.game_time == "evening"

    def test_advance_clock_night(self, game_state):
        game_state.advance_clock(3)  # 3 AM
        assert game_state.game_time == "night"

    def test_advance_clock_wraps_around_midnight(self, game_state):
        game_state.advance_clock(25)  # 25 hours => 1 AM next day
        assert game_state.game_time == "night"

    def test_advance_clock_accumulates(self, game_state):
        game_state.advance_clock(6)
        game_state.advance_clock(6)
        assert game_state.game_clock == 12.0
