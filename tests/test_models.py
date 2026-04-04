"""Tests for models: BaseModel, Character, NPCCard, Location, Setting."""

from __future__ import annotations

import pytest

from models.base_model import BaseModel
from models.character import Character
from models.npc_card import NPCCard
from models.setting import Setting

_DAGGER = "dagger"
_NPC_A = "npc-1"
_UUID_LENGTH = 36


class TestBaseModel:
    def test_uuid_generated_on_init(self):
        model = BaseModel()
        assert isinstance(model.uuid, str)
        assert len(model.uuid) == _UUID_LENGTH

    def test_unique_uuids(self):
        uuids = {BaseModel().uuid for _ in range(100)}
        assert len(uuids) == 100


class TestCharacter:
    def test_defaults(self):
        char = Character(name="Livia")
        assert char.name == "Livia"
        assert char.biography == ""
        assert char.relationships == {}
        assert char.attributes == {}
        assert char.inventory == []

    def test_default_personality_and_scope(self):
        char = Character(name="Livia")
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


class TestNPCCard:
    def test_to_prompt_context_contains_name(self, sample_npc):
        assert "Marcus" in sample_npc.to_prompt_context()

    def test_to_prompt_context_contains_occupation(self, sample_npc):
        assert "Soldier" in sample_npc.to_prompt_context()

    def test_to_prompt_context_contains_traits(self, sample_npc):
        ctx = sample_npc.to_prompt_context()
        assert "brave" in ctx
        assert "loyal" in ctx

    def test_to_prompt_context_shows_inventory(self, sample_npc):
        ctx = sample_npc.to_prompt_context()
        assert "gladius" in ctx
        assert "scutum" in ctx

    def test_to_prompt_context_shows_attributes(self, sample_npc):
        assert "strength=8" in sample_npc.to_prompt_context()

    def test_conversation_history_starts_empty(self, sample_npc):
        assert sample_npc.conversation_history == []

    def test_current_mood_default(self, sample_npc):
        assert sample_npc.current_mood == "neutral"


class TestNPCCardPhysicalStatus:
    def test_default_is_healthy(self, sample_npc):
        assert sample_npc.physical_status == "healthy"

    def test_custom_value(self):
        npc = NPCCard(name="Brutus", occupation="senator", physical_status="wounded left arm")
        assert npc.physical_status == "wounded left arm"

    def test_prompt_has_status(self, sample_npc):
        assert "Physical status: healthy" in sample_npc.to_prompt_context()

    def test_prompt_has_custom_status(self):
        npc = NPCCard(name="Brutus", occupation="senator", physical_status="barely standing")
        assert "Physical status: barely standing" in npc.to_prompt_context()


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
        sample_location.remove_npc("ghost")


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

    def test_optional_metadata_defaults_empty(self):
        setting = Setting(name="X", time_period="Y", region="Z", summary="S")
        assert setting.traditions == []
        assert setting.technologies == []
        assert setting.raw_sources == []

    def test_key_persons_stored(self, simple_setting):
        assert simple_setting.key_persons[0]["name"] == "Augustus"

    def test_has_uuid(self, simple_setting):
        assert isinstance(simple_setting.uuid, str) and len(simple_setting.uuid) == _UUID_LENGTH
