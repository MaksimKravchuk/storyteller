"""Tests for models: BaseModel, Character, NPCCard, Location, Setting."""

from __future__ import annotations

import uuid as uuid_mod
from types import SimpleNamespace

import allure
import pytest
from pydantic import ValidationError

from models.base_model import StorytellerBase
from models.character import Character
from models.location import Location
from models.npc_card import NPCCard
from models.setting import Setting

_DAGGER = "dagger"
_NPC_A = "npc-1"


def _fake_game_state(known_npcs: set[str] | None = None) -> SimpleNamespace:
    """Minimal stand-in for ``GameState`` used by label-for-player tests."""
    return SimpleNamespace(player=SimpleNamespace(known_npcs=known_npcs or set()))


@allure.epic("Memory & Persistence")
@allure.feature("Domain models")
class TestBaseModel:
    @allure.story("BaseModel UUID")
    @allure.title("StorytellerBase assigns a UUID on construction")
    def test_uuid_generated_on_init(self):
        model = StorytellerBase()
        assert isinstance(model.uuid, uuid_mod.UUID)

    @allure.story("BaseModel UUID")
    @allure.title("100 StorytellerBase instances produce 100 unique UUIDs")
    def test_unique_uuids(self):
        uuids = {StorytellerBase().uuid for _ in range(100)}
        assert len(uuids) == 100

    @allure.story("BaseModel UUID")
    @allure.title("StorytellerBase generates a uuid.UUID with version 4")
    def test_uuid_is_uuid4_instance(self):
        model = StorytellerBase()
        assert isinstance(model.uuid, uuid_mod.UUID)
        assert model.uuid.version == 4

    @allure.story("BaseModel UUID")
    @allure.title("Constructing with a non-UUID string raises ValidationError")
    def test_invalid_uuid_rejected(self):
        with pytest.raises(ValidationError):
            StorytellerBase(uuid="guard")


@allure.epic("Memory & Persistence")
@allure.feature("Domain models")
class TestCharacter:
    @allure.story("Character defaults")
    @allure.title("A Character with only a name has empty biography, relationships, attributes, and inventory")
    def test_defaults(self):
        char = Character(name="Livia")
        assert char.name == "Livia"
        assert char.biography == ""
        assert char.relationships == {}
        assert char.attributes == {}
        assert char.inventory == []

    @allure.story("Character defaults")
    @allure.title("A new Character has empty personality traits and defaults to 'local' knowledge scope")
    def test_default_personality_and_scope(self):
        char = Character(name="Livia")
        assert char.personality_traits == []
        assert char.knowledge_scope == "local"

    @allure.story("Character attributes")
    @allure.title("Character.update_attribute and get_attribute round-trip values and honor default fallbacks")
    def test_update_and_get_attribute(self):
        char = Character(name="Cato")
        char.update_attribute("strength", 7)
        assert char.get_attribute("strength") == 7
        assert char.get_attribute("wisdom", default=5) == 5

    @allure.story("Character inventory")
    @allure.title("Character inventory supports adding and removing items")
    def test_inventory_add_and_remove(self):
        char = Character(name="Cassius")
        char.add_item_to_inventory(_DAGGER)
        assert _DAGGER in char.inventory
        char.remove_item_from_inventory(_DAGGER)
        assert _DAGGER not in char.inventory

    @allure.story("Character inventory")
    @allure.title("Removing an item not present in inventory raises ValueError naming the missing item")
    def test_remove_item_not_in_inventory_raises(self):
        char = Character(name="Cassius")
        with pytest.raises(ValueError, match=_DAGGER):
            char.remove_item_from_inventory("dagger")


@allure.epic("Memory & Persistence")
@allure.feature("Domain models")
class TestNPCCard:
    @allure.story("NPCCard fields")
    @allure.title("A new NPCCard starts with an empty conversation history list")
    def test_conversation_history_starts_empty(self, sample_npc):
        assert sample_npc.conversation_history == []

    @allure.story("NPCCard fields")
    @allure.title("A new NPCCard defaults to a 'neutral' current mood")
    def test_current_mood_default(self, sample_npc):
        assert sample_npc.current_mood == "neutral"


@allure.epic("Narrative Delivery")
@allure.feature("NPC label formatting")
class TestNPCCardLabelForPlayer:
    """``NPCCard.label_for_player`` gates name reveals on ``PlayerState.known_npcs``.

    Used by the Narrator (scene's ``npcs_present`` line) and the plan
    executor (``raw_outputs.new_npcs``). The three branches are
    exercised here against a minimal stand-in for ``GameState`` so the
    model test suite does not pull in full-game fixtures.
    """

    @allure.story("Known NPC")
    @allure.title("label_for_player returns 'Name (Occupation)' when the NPC's UUID is in player.known_npcs")
    def test_known_npc_renders_name_and_occupation(self):
        npc = NPCCard(
            name="Marcus",
            occupation="centurion",
            short_descriptor="a tall man in a red cloak",
        )
        gs = _fake_game_state({npc.uuid})

        assert npc.label_for_player(gs, role_fallback="soldier") == "Marcus (centurion)"

    @allure.story("Known NPC")
    @allure.title("label_for_player returns the bare name when an introduced NPC has no occupation")
    def test_known_npc_without_occupation_drops_empty_parentheses(self):
        npc = NPCCard(name="Marcus")
        gs = _fake_game_state({npc.uuid})

        assert npc.label_for_player(gs, role_fallback="soldier") == "Marcus"

    @allure.story("Unknown NPC")
    @allure.title("label_for_player returns the short_descriptor when the NPC is not yet introduced")
    def test_unknown_npc_with_descriptor_returns_descriptor(self):
        npc = NPCCard(
            name="Marcus",
            occupation="centurion",
            short_descriptor="a tall man in a red cloak",
        )
        gs = _fake_game_state()

        assert npc.label_for_player(gs, role_fallback="soldier") == "a tall man in a red cloak"

    @allure.story("Unknown NPC")
    @allure.title("label_for_player falls back to role when the card has no short_descriptor")
    def test_unknown_npc_without_descriptor_falls_back_to_role(self):
        npc = NPCCard(name="Marcus", occupation="centurion")
        gs = _fake_game_state()

        assert npc.label_for_player(gs, role_fallback="soldier") == "soldier"


@allure.epic("Memory & Persistence")
@allure.feature("Domain models")
class TestNPCCardPhysicalStatus:
    @allure.story("NPCCard physical status")
    @allure.title("A new NPCCard defaults to a 'healthy' physical status")
    def test_default_is_healthy(self, sample_npc):
        assert sample_npc.physical_status == "healthy"

    @allure.story("NPCCard physical status")
    @allure.title("NPCCard accepts a free-form multi-word physical status like 'wounded left arm'")
    def test_custom_value(self):
        npc = NPCCard(name="Brutus", occupation="senator", physical_status="wounded left arm")
        assert npc.physical_status == "wounded left arm"


@allure.epic("Memory & Persistence")
@allure.feature("Domain models")
class TestLocation:
    @allure.story("Location defaults")
    @allure.title("A new Location has its name set and empty npcs_present and points_of_interest lists")
    def test_defaults(self, sample_location):
        assert sample_location.name == "Forum Romanum"
        assert sample_location.npcs_present == []
        assert sample_location.points_of_interest == []

    @allure.story("Location NPC membership")
    @allure.title("Location.add_npc places the NPC UUID into the npcs_present list")
    def test_add_npc(self, sample_location):
        sample_location.add_npc(_NPC_A)
        assert _NPC_A in sample_location.npcs_present

    @allure.story("Location NPC membership")
    @allure.title("Adding the same NPC twice to a Location is idempotent and keeps a single entry")
    def test_add_npc_idempotent(self, sample_location):
        sample_location.add_npc(_NPC_A)
        sample_location.add_npc(_NPC_A)
        assert sample_location.npcs_present.count(_NPC_A) == 1

    @allure.story("Location NPC membership")
    @allure.title("Location.remove_npc drops the NPC UUID from the npcs_present list")
    def test_remove_npc(self, sample_location):
        sample_location.add_npc(_NPC_A)
        sample_location.remove_npc(_NPC_A)
        assert _NPC_A not in sample_location.npcs_present

    @allure.story("Location NPC membership")
    @allure.title("Removing an NPC not currently in the Location is a silent no-op")
    def test_remove_npc_not_present_is_noop(self, sample_location):
        sample_location.remove_npc("ghost")

    @allure.story("Location object state")
    @allure.title("record_object_state writes a normalized entry into object_states and returns True")
    def test_record_object_state_writes_normalized_key(self, sample_location):
        wrote = sample_location.record_object_state("Wooden_Shutter", "splintered")
        assert wrote is True
        assert sample_location.object_states == {"wooden shutter": "splintered"}

    @allure.story("Location object state")
    @allure.title("record_object_state collapses snake_case and mixed-case keys to the same slot")
    def test_record_object_state_collapses_paraphrases(self, sample_location):
        sample_location.record_object_state("wooden_shutter", "cracked")
        sample_location.record_object_state("Wooden Shutter", "splintered")
        assert sample_location.object_states == {"wooden shutter": "splintered"}

    @allure.story("Location object state")
    @allure.title("record_object_state returns False without writing when the key is empty or whitespace")
    def test_record_object_state_empty_key(self, sample_location):
        assert sample_location.record_object_state("", "splintered") is False
        assert sample_location.record_object_state("   ", "splintered") is False
        assert sample_location.object_states == {}

    @allure.story("Location object state")
    @allure.title("record_object_state returns False without writing when the state description is empty")
    def test_record_object_state_empty_description(self, sample_location):
        assert sample_location.record_object_state("shutter", "") is False
        assert sample_location.object_states == {}

    @allure.story("Location object state")
    @allure.title("A new Location starts with an empty object_states dict that is independent per instance")
    def test_object_states_default_per_instance(self):
        first = Location(name="A")
        second = Location(name="B")
        first.object_states["shutter"] = "splintered"
        assert second.object_states == {}


@allure.epic("Memory & Persistence")
@allure.feature("Domain models")
class TestSetting:
    @allure.story("Setting fields")
    @allure.title("A Setting stores its required name, time_period, and region fields")
    def test_required_fields(self, simple_setting):
        assert simple_setting.name == "Ancient Rome"
        assert simple_setting.time_period == "1st century AD"
        assert simple_setting.region == "Italy"

    @allure.story("Setting fields")
    @allure.title("A new Setting has empty key_persons, key_events, and locations lists by default")
    def test_optional_lists_default_empty(self):
        setting = Setting(name="X", time_period="Y", region="Z", summary="S")
        assert setting.key_persons == []
        assert setting.key_events == []
        assert setting.locations == []

    @allure.story("Setting fields")
    @allure.title("A new Setting has empty traditions and technologies metadata lists")
    def test_optional_metadata_defaults_empty(self):
        setting = Setting(name="X", time_period="Y", region="Z", summary="S")
        assert setting.traditions == []
        assert setting.technologies == []

    @allure.story("Setting fields")
    @allure.title("A Setting preserves key_persons entries as supplied dictionaries")
    def test_key_persons_stored(self, simple_setting):
        assert simple_setting.key_persons[0]["name"] == "Augustus"

    @allure.story("Setting fields")
    @allure.title("A Setting inherits a UUID from BaseModel")
    def test_has_uuid(self, simple_setting):
        assert isinstance(simple_setting.uuid, uuid_mod.UUID)
