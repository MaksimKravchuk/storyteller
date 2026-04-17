"""Round-trip tests for db/converters/*.

These converters are the sole bridge between domain models and ORM rows, so
each one must survive a domain→row→domain round-trip without losing fields.
Covers event, knowledge, location, npc, player, scene, setting.
"""

from __future__ import annotations

import allure
import pytest

from db.converters import (
    event as ev_conv,
    knowledge as kn_conv,
    location as loc_conv,
    npc as npc_conv,
    player as pl_conv,
    scene as sc_conv,
    setting as st_conv,
)
from knowledge.node import CanonSource, KnowledgeNode, KnowledgeScope, KnowledgeSource
from models import game_state, location, npc_card, scene, setting
from timeline import event as timeline_event

GAME_STATE_ID = "gs-1"


@allure.epic("Persistence")
@allure.feature("Domain↔row converters")
class TestSettingConverter:
    @allure.story("Round-trip")
    @allure.title("Setting survives a domain→row→domain round-trip preserving every field")
    def test_round_trip(self):
        original = setting.Setting(
            name="Rome",
            time_period="1 AD",
            region="Italy",
            summary="Eternal city",
            key_persons=[{"name": "Caesar", "role": "dictator"}],
            key_events=[{"name": "Crossing the Rubicon", "date": "49 BC"}],
            locations=[{"name": "Forum", "type": "square"}],
            traditions=["toga"],
            technologies=["aqueducts"],
            social_structure="patrician/plebeian",
            raw_sources=["wikipedia"],
        )
        row = st_conv.setting_to_row(original, GAME_STATE_ID)
        assert row["game_state_id"] == GAME_STATE_ID

        restored = st_conv.row_to_setting(row)
        assert restored.uuid == original.uuid
        assert restored.name == original.name
        assert restored.time_period == original.time_period
        assert restored.region == original.region
        assert restored.summary == original.summary
        assert restored.key_persons == original.key_persons
        assert restored.key_events == original.key_events
        assert restored.locations == original.locations
        assert restored.traditions == original.traditions
        assert restored.technologies == original.technologies
        assert restored.social_structure == original.social_structure
        assert restored.raw_sources == original.raw_sources


@allure.epic("Persistence")
@allure.feature("Domain↔row converters")
class TestLocationConverter:
    @allure.story("Round-trip")
    @allure.title("Location round-trips including npcs_present, points_of_interest, and object_states")
    def test_round_trip(self):
        loc = location.Location(
            name="Market",
            description="A bustling market",
            parent_location_id="city-1",
            location_type="district",
            tags=["commerce"],
            connected_locations=["loc-a", "loc-b"],
        )
        loc.npcs_present = ["npc-1", "npc-2"]
        loc.points_of_interest = ["fountain", "statue"]
        loc.object_states = {"shutter": "splintered; frame torn loose"}

        row = loc_conv.location_to_row(loc, GAME_STATE_ID)
        assert row["game_state_id"] == GAME_STATE_ID

        restored = loc_conv.row_to_location(row)
        assert restored.uuid == loc.uuid
        assert restored.name == "Market"
        assert restored.description == "A bustling market"
        assert restored.parent_location_id == "city-1"
        assert restored.location_type == "district"
        assert restored.tags == ["commerce"]
        assert restored.connected_locations == ["loc-a", "loc-b"]
        assert restored.npcs_present == ["npc-1", "npc-2"]
        assert restored.points_of_interest == ["fountain", "statue"]
        assert restored.object_states == {"shutter": "splintered; frame torn loose"}


@allure.epic("Persistence")
@allure.feature("Domain↔row converters")
class TestNPCConverter:
    @allure.story("Round-trip")
    @allure.title("NPCCard round-trips with all identity, state, and history fields")
    def test_round_trip(self):
        npc = npc_card.NPCCard(
            name="Marcus",
            biography="A veteran legionnaire",
            appearance="Scarred",
            short_descriptor="a scarred man in legionary mail",
            occupation="guard",
            personality_traits=["stoic", "loyal"],
            speech_style="terse",
            knowledge_scope="city",
            attributes={"strength": 8},
            inventory=["sword", "shield"],
            location_id="loc-1",
            relationships={"npc-2": "friend"},
        )
        npc.conversation_history = [{"role": "user", "content": "hi"}]
        npc.current_mood = "suspicious"
        npc.physical_status = "wounded"
        npc.hostility_level = 4
        npc.recent_hostile_actions = [
            {"turn": "7", "action": "player punched you", "severity": "high"},
        ]

        row = npc_conv.npc_to_row(npc, GAME_STATE_ID)
        assert row["game_state_id"] == GAME_STATE_ID

        restored = npc_conv.row_to_npc(row)
        assert restored.uuid == npc.uuid
        assert restored.name == "Marcus"
        assert restored.biography == "A veteran legionnaire"
        assert restored.appearance == "Scarred"
        assert restored.short_descriptor == "a scarred man in legionary mail"
        assert restored.occupation == "guard"
        assert restored.personality_traits == ["stoic", "loyal"]
        assert restored.speech_style == "terse"
        assert restored.knowledge_scope == "city"
        assert restored.attributes == {"strength": 8}
        assert restored.inventory == ["sword", "shield"]
        assert restored.location_id == "loc-1"
        assert restored.relationships == {"npc-2": "friend"}
        assert restored.conversation_history == [{"role": "user", "content": "hi"}]
        assert restored.current_mood == "suspicious"
        assert restored.physical_status == "wounded"
        assert restored.hostility_level == 4
        assert restored.recent_hostile_actions == [
            {"turn": "7", "action": "player punched you", "severity": "high"},
        ]

    @allure.story("Backwards compatibility")
    @allure.title("row_to_npc defaults physical_status to 'healthy' on legacy rows lacking that column")
    def test_physical_status_defaults_on_legacy_row(self):
        npc = npc_card.NPCCard(name="Legacy")
        row = npc_conv.npc_to_row(npc, GAME_STATE_ID)
        row.pop("physical_status")

        restored = npc_conv.row_to_npc(row)
        assert restored.physical_status == "healthy"

    @allure.story("Backwards compatibility")
    @allure.title("row_to_npc defaults hostility fields on legacy rows lacking those columns")
    def test_hostility_defaults_on_legacy_row(self):
        npc = npc_card.NPCCard(name="Legacy")
        row = npc_conv.npc_to_row(npc, GAME_STATE_ID)
        row.pop("hostility_level")
        row.pop("recent_hostile_actions")

        restored = npc_conv.row_to_npc(row)
        assert restored.hostility_level == 0
        assert restored.recent_hostile_actions == []

    @allure.story("Backwards compatibility")
    @allure.title("row_to_npc defaults short_descriptor to empty string on legacy rows lacking the column")
    def test_short_descriptor_defaults_on_legacy_row(self):
        npc = npc_card.NPCCard(name="Legacy")
        row = npc_conv.npc_to_row(npc, GAME_STATE_ID)
        row.pop("short_descriptor")

        restored = npc_conv.row_to_npc(row)
        assert restored.short_descriptor == ""


@allure.epic("Persistence")
@allure.feature("Domain↔row converters")
class TestPlayerConverter:
    @allure.story("Round-trip")
    @allure.title("PlayerState round-trips including inventory and interaction history")
    def test_round_trip(self):
        player = game_state.PlayerState(name="Hero")
        player.location_id = "loc-42"
        player.inventory = ["torch", "map"]
        player.appearance = "A weary adventurer"
        player.interaction_history = [{"turn": 1, "action": "look"}]
        player.physical_status = "exhausted"
        player.known_npcs = {"npc-1", "npc-2"}
        player.player_event_log = ["Met Marcus", "Found the shrine"]
        player.learned_facts = {"fact-a", "fact-b"}

        row = pl_conv.player_to_row(player, GAME_STATE_ID)
        assert row["game_state_id"] == GAME_STATE_ID
        assert row["known_npcs"] == ["npc-1", "npc-2"]
        assert row["player_event_log"] == ["Met Marcus", "Found the shrine"]
        assert row["learned_facts"] == ["fact-a", "fact-b"]

        restored = pl_conv.row_to_player(row)
        assert restored.uuid == player.uuid
        assert restored.name == "Hero"
        assert restored.location_id == "loc-42"
        assert restored.inventory == ["torch", "map"]
        assert restored.appearance == "A weary adventurer"
        assert restored.interaction_history == [{"turn": 1, "action": "look"}]
        assert restored.physical_status == "exhausted"
        assert restored.known_npcs == {"npc-1", "npc-2"}
        assert restored.player_event_log == ["Met Marcus", "Found the shrine"]
        assert restored.learned_facts == {"fact-a", "fact-b"}

    @allure.story("Backwards compatibility")
    @allure.title("row_to_player defaults physical_status to 'healthy' on legacy rows lacking that column")
    def test_physical_status_defaults_on_legacy_row(self):
        player = game_state.PlayerState(name="Legacy")
        row = pl_conv.player_to_row(player, GAME_STATE_ID)
        row.pop("physical_status")

        restored = pl_conv.row_to_player(row)
        assert restored.physical_status == "healthy"

    @allure.story("Backwards compatibility")
    @allure.title("row_to_player defaults knowledge fields to empty on legacy rows lacking those columns")
    def test_knowledge_fields_default_on_legacy_row(self):
        player = game_state.PlayerState(name="Legacy")
        row = pl_conv.player_to_row(player, GAME_STATE_ID)
        row.pop("known_npcs")
        row.pop("player_event_log")
        row.pop("learned_facts")

        restored = pl_conv.row_to_player(row)
        assert restored.known_npcs == set()
        assert restored.player_event_log == []
        assert restored.learned_facts == set()


@allure.epic("Persistence")
@allure.feature("Domain↔row converters")
class TestSceneConverter:
    @allure.story("Round-trip")
    @allure.title("Scene round-trips preserving SceneNPC role/uuid pairs via to_dict serialization")
    def test_round_trip(self):
        original = scene.Scene(
            location_id="loc-1",
            description="A quiet square",
            npcs_present=[scene.SceneNPC(role="guard", uuid="npc-1")],
            points_of_interest=["well"],
            ambient_description="Birds chirp",
            time_of_day="dawn",
        )
        original.narrated_text = "You stand in a quiet square at dawn."

        row = sc_conv.scene_to_row(original, GAME_STATE_ID, is_current=True, scene_number=3)
        assert row["game_state_id"] == GAME_STATE_ID
        assert row["is_current"] is True
        assert row["scene_number"] == 3
        assert row["npcs_present"] == [{"role": "guard", "uuid": "npc-1"}]

        restored = sc_conv.row_to_scene(row)
        assert restored.uuid == original.uuid
        assert restored.location_id == "loc-1"
        assert restored.description == "A quiet square"
        assert len(restored.npcs_present) == 1
        assert restored.npcs_present[0].role == "guard"
        assert restored.npcs_present[0].uuid == "npc-1"
        assert restored.points_of_interest == ["well"]
        assert restored.ambient_description == "Birds chirp"
        assert restored.time_of_day == "dawn"
        assert restored.narrated_text == "You stand in a quiet square at dawn."

    @allure.story("Backwards compatibility")
    @allure.title("row_to_scene handles legacy rows where npcs_present entries are bare UUID strings")
    def test_legacy_string_npcs_present(self):
        original = scene.Scene(location_id="loc-1")
        row = sc_conv.scene_to_row(original, GAME_STATE_ID)
        row["npcs_present"] = ["npc-legacy-uuid"]

        restored = sc_conv.row_to_scene(row)
        assert len(restored.npcs_present) == 1
        assert restored.npcs_present[0].role == "npc-legacy-uuid"
        assert restored.npcs_present[0].uuid == "npc-legacy-uuid"


@allure.epic("Persistence")
@allure.feature("Domain↔row converters")
class TestKnowledgeConverter:
    @allure.story("Round-trip")
    @allure.title("KnowledgeNode round-trips preserving scope, source, canon, and gating fields")
    def test_round_trip(self):
        node = KnowledgeNode(
            text="The king was poisoned",
            scope=KnowledgeScope.COUNTRY,
            source=KnowledgeSource.RUMOR,
            canon=CanonSource.SESSION,
            required_education=5,
            required_social_status=3,
            tags=["politics", "scandal"],
            location_id="loc-court",
            timestamp=12.5,
            confidence=0.6,
        )
        row = kn_conv.knowledge_node_to_row(node, GAME_STATE_ID)
        assert row["game_state_id"] == GAME_STATE_ID
        assert row["canon"] == "session"

        restored = kn_conv.row_to_knowledge_node(row)
        assert restored.uuid == node.uuid
        assert restored.text == "The king was poisoned"
        assert restored.scope == KnowledgeScope.COUNTRY
        assert restored.source == KnowledgeSource.RUMOR
        assert restored.canon == CanonSource.SESSION
        assert restored.required_education == 5
        assert restored.required_social_status == 3
        assert restored.tags == ["politics", "scandal"]
        assert restored.location_id == "loc-court"
        assert restored.timestamp == pytest.approx(12.5)
        assert restored.confidence == pytest.approx(0.6)

    @allure.story("Backwards compatibility")
    @allure.title("row_to_knowledge_node defaults canon to HISTORICAL on legacy rows missing the column")
    def test_canon_defaults_on_legacy_row(self):
        node = KnowledgeNode(text="Legacy fact")
        row = kn_conv.knowledge_node_to_row(node, GAME_STATE_ID)
        row.pop("canon")

        restored = kn_conv.row_to_knowledge_node(row)
        assert restored.canon == CanonSource.HISTORICAL


@allure.epic("Persistence")
@allure.feature("Domain↔row converters")
class TestGameEventConverter:
    @allure.story("Round-trip")
    @allure.title("GameEvent round-trips preserving effects, status, and completes_at")
    def test_round_trip(self):
        effect = timeline_event.EventEffect(
            effect_type="MOVE_NPC",
            target_id="npc-1",
            effect_data={"npc_id": "npc-1", "to_location_id": "loc-2"},
        )
        event_obj = timeline_event.GameEvent(
            name="guard patrol",
            scheduled_at=10,
            duration=2,
            owner_id="npc-1",
            location_id="loc-1",
            scope="local",
            effects=[effect],
            follow_up_events=[{"name": "shift change"}],
            on_complete_description="The guard arrives at the gate.",
        )
        event_obj.status = timeline_event.EventStatus.COMPLETED

        row = ev_conv.game_event_to_row(event_obj, GAME_STATE_ID)
        assert row["game_state_id"] == GAME_STATE_ID
        assert row["completes_at"] == pytest.approx(12)
        assert row["status"] == "completed"
        assert row["effects"][0]["effect_type"] == "MOVE_NPC"

        restored = ev_conv.row_to_game_event(row)
        assert restored.uuid == event_obj.uuid
        assert restored.name == "guard patrol"
        assert restored.scheduled_at == pytest.approx(10)
        assert restored.duration == pytest.approx(2)
        assert restored.completes_at == pytest.approx(12)
        assert restored.owner_id == "npc-1"
        assert restored.location_id == "loc-1"
        assert restored.scope == "local"
        assert restored.status == timeline_event.EventStatus.COMPLETED
        assert len(restored.effects) == 1
        assert restored.effects[0].effect_type == "MOVE_NPC"
        assert restored.effects[0].target_id == "npc-1"
        assert restored.effects[0].effect_data == {"npc_id": "npc-1", "to_location_id": "loc-2"}
        assert restored.follow_up_events == [{"name": "shift change"}]
        assert restored.on_complete_description == "The guard arrives at the gate."

    @allure.story("Backwards compatibility")
    @allure.title("row_to_game_event reads legacy 'params' effect payloads as effect_data")
    def test_legacy_params_key(self):
        event_obj = timeline_event.GameEvent(
            name="legacy",
            scheduled_at=0,
            duration=1,
            effects=[
                timeline_event.EventEffect(
                    effect_type="CHANGE_STATUS",
                    target_id="npc-1",
                    effect_data={},
                ),
            ],
        )
        row = ev_conv.game_event_to_row(event_obj, GAME_STATE_ID)
        # Simulate an old row written before we renamed params → effect_data.
        row["effects"] = [
            {"effect_type": "CHANGE_STATUS", "target_id": "npc-1", "params": {"status": "wounded"}},
        ]

        restored = ev_conv.row_to_game_event(row)
        assert restored.effects[0].effect_data == {"status": "wounded"}
