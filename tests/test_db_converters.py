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
from models.goal import Goal, GoalKind, GoalScope, GoalStatus
from models.relationship import Relationship, RelationshipKind
from tests._uuid_helpers import make_uuid
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


@allure.epic("Persistence")
@allure.feature("Domain↔row converters")
class TestLocationConverter:
    @allure.story("Round-trip")
    @allure.title("Location round-trips including npcs_present, points_of_interest, and object_states")
    def test_round_trip(self):
        loc = location.Location(
            name="Market",
            description="A bustling market",
            parent_location_id=make_uuid("city-1"),
            location_type="district",
            tags=["commerce"],
            connected_locations=[make_uuid("loc-a"), make_uuid("loc-b")],
        )
        loc.npcs_present = [make_uuid("npc-1"), make_uuid("npc-2")]
        loc.points_of_interest = ["fountain", "statue"]
        loc.object_states = {"shutter": "splintered; frame torn loose"}

        row = loc_conv.location_to_row(loc, GAME_STATE_ID)
        assert row["game_state_id"] == GAME_STATE_ID
        # points_of_interest dumped with mode="json": each POI's UUID is a plain str, not a UUID.
        assert isinstance(row["points_of_interest"][0]["uuid"], str)
        assert [poi["names"][0] for poi in row["points_of_interest"]] == ["fountain", "statue"]

        restored = loc_conv.row_to_location(row)
        assert restored.uuid == loc.uuid
        assert restored.name == "Market"
        assert restored.description == "A bustling market"
        assert restored.parent_location_id == make_uuid("city-1")
        assert restored.location_type == "district"
        assert restored.tags == ["commerce"]
        assert restored.connected_locations == [make_uuid("loc-a"), make_uuid("loc-b")]
        assert restored.npcs_present == [make_uuid("npc-1"), make_uuid("npc-2")]
        assert [poi.primary_name for poi in restored.points_of_interest] == ["fountain", "statue"]
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
            location_id=make_uuid("loc-1"),
            relationships=[Relationship(target_uuid="npc-2", kind=RelationshipKind.FRIEND)],
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
        # relationships_to_row dumps with mode="json": the relationship's own UUID must be a
        # plain JSON str, not a UUID object — mode=None/other modes leave it a UUID.
        rel_row = row["relationships"][0]
        assert isinstance(rel_row["uuid"], str)
        assert rel_row["kind"] == "friend"

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
        assert restored.location_id == make_uuid("loc-1")
        assert len(restored.relationships) == 1
        assert restored.relationships[0].target_uuid == "npc-2"
        assert restored.relationships[0].kind == RelationshipKind.FRIEND
        assert restored.conversation_history == [{"role": "user", "content": "hi"}]
        assert restored.current_mood == "suspicious"
        assert restored.physical_status == "wounded"
        assert restored.hostility_level == 4
        assert restored.recent_hostile_actions == [
            {"turn": "7", "action": "player punched you", "severity": "high"},
        ]

    @allure.story("Round-trip")
    @allure.title("life_goal and tactical_goal Goal objects survive a domain→row→domain round-trip")
    def test_goal_round_trip(self):
        npc = npc_card.NPCCard(name="Marcus")
        npc.life_goal = Goal(
            scope=GoalScope.LIFE,
            kind=GoalKind.KILL,
            description="Avenge brother",
            target_uuid=make_uuid("npc-9"),
            progress_notes=["spotted target near the bridge"],
        )
        npc.tactical_goal = Goal(
            scope=GoalScope.TACTICAL,
            kind=GoalKind.FLEE_SCENE,
            description="Escape the city watch",
            status=GoalStatus.ACTIVE,
            turns_pursued=2,
            created_on_turn=14,
        )

        row = npc_conv.npc_to_row(npc, GAME_STATE_ID)
        assert row["life_goal"]["kind"] == "kill"
        assert row["life_goal"]["scope"] == "life"
        assert row["tactical_goal"]["scope"] == "tactical"
        # mode="json" must JSON-serialise the goal's UUID target to a plain str, not a UUID object.
        assert isinstance(row["life_goal"]["target_uuid"], str)
        assert row["life_goal"]["target_uuid"] == str(make_uuid("npc-9"))

        restored = npc_conv.row_to_npc(row)
        assert restored.life_goal == npc.life_goal
        assert restored.tactical_goal == npc.tactical_goal

    @allure.story("Round-trip")
    @allure.title("NPCs with no goals round-trip with life_goal and tactical_goal as None")
    def test_goal_none_round_trip(self):
        npc = npc_card.NPCCard(name="No-goal")
        row = npc_conv.npc_to_row(npc, GAME_STATE_ID)
        assert row["life_goal"] is None
        assert row["tactical_goal"] is None

        restored = npc_conv.row_to_npc(row)
        assert restored.life_goal is None
        assert restored.tactical_goal is None

    @allure.story("Backwards compatibility")
    @allure.title("row_to_npc upcasts a legacy dict[str, str] relationships payload to list[Relationship]")
    def test_legacy_dict_relationships_upcast(self):
        npc = npc_card.NPCCard(name="Legacy")
        row = npc_conv.npc_to_row(npc, GAME_STATE_ID)
        row["relationships"] = {"npc-enemy": "murderous_enemy", "npc-friend": "trusted friend"}

        restored = npc_conv.row_to_npc(row)
        assert len(restored.relationships) == 2
        by_target = {r.target_uuid: r for r in restored.relationships}
        assert by_target["npc-enemy"].kind == RelationshipKind.ENEMY
        assert by_target["npc-friend"].kind == RelationshipKind.NEUTRAL
        # Hostile labels upcast to intensity -3; non-hostile to 0 — guards the signed branch.
        assert by_target["npc-enemy"].intensity == -3
        assert by_target["npc-friend"].intensity == 0
        # The legacy label is preserved verbatim as the relationship note.
        assert by_target["npc-enemy"].note == "murderous_enemy"
        assert by_target["npc-friend"].note == "trusted friend"

    @allure.story("Backwards compatibility")
    @allure.title("row_to_npc upcasts a legacy relationship with a falsy label to an empty-string note")
    def test_legacy_dict_relationships_falsy_label(self):
        npc = npc_card.NPCCard(name="Legacy")
        row = npc_conv.npc_to_row(npc, GAME_STATE_ID)
        row["relationships"] = {"npc-blank": None, "npc-empty": ""}

        restored = npc_conv.row_to_npc(row)
        by_target = {r.target_uuid: r for r in restored.relationships}
        # A falsy legacy label normalises to "" (not a placeholder) and stays NEUTRAL.
        assert by_target["npc-blank"].note == ""
        assert by_target["npc-empty"].note == ""
        assert by_target["npc-blank"].kind == RelationshipKind.NEUTRAL
        assert by_target["npc-blank"].intensity == 0

    @allure.story("Backwards compatibility")
    @allure.title("row_to_npc defaults goal columns to None on legacy rows lacking those columns")
    def test_goal_defaults_on_legacy_row(self):
        npc = npc_card.NPCCard(name="Legacy")
        row = npc_conv.npc_to_row(npc, GAME_STATE_ID)
        row.pop("life_goal")
        row.pop("tactical_goal")

        restored = npc_conv.row_to_npc(row)
        assert restored.life_goal is None
        assert restored.tactical_goal is None


@allure.epic("Persistence")
@allure.feature("Domain↔row converters")
class TestPlayerConverter:
    @allure.story("Round-trip")
    @allure.title("PlayerState round-trips including inventory and known NPCs")
    def test_round_trip(self):
        player = game_state.PlayerState(name="Hero")
        player.location_id = make_uuid("loc-42")
        player.inventory = ["torch", "map"]
        player.appearance = "A weary adventurer"
        player.physical_status = "exhausted"
        player.known_npcs = {make_uuid("npc-1"), make_uuid("npc-2")}
        player.player_event_log = ["Met Marcus", "Found the shrine"]
        player.learned_facts = {make_uuid("fact-a"), make_uuid("fact-b")}

        row = pl_conv.player_to_row(player, GAME_STATE_ID)
        assert row["game_state_id"] == GAME_STATE_ID
        assert set(row["known_npcs"]) == {str(make_uuid("npc-1")), str(make_uuid("npc-2"))}
        assert row["player_event_log"] == ["Met Marcus", "Found the shrine"]
        assert set(row["learned_facts"]) == {str(make_uuid("fact-a")), str(make_uuid("fact-b"))}

        restored = pl_conv.row_to_player(row)
        assert restored.uuid == player.uuid
        assert restored.name == "Hero"
        assert restored.location_id == make_uuid("loc-42")
        assert restored.inventory == ["torch", "map"]
        assert restored.appearance == "A weary adventurer"
        assert restored.physical_status == "exhausted"
        assert restored.known_npcs == {make_uuid("npc-1"), make_uuid("npc-2")}
        assert restored.player_event_log == ["Met Marcus", "Found the shrine"]
        assert restored.learned_facts == {make_uuid("fact-a"), make_uuid("fact-b")}


@allure.epic("Persistence")
@allure.feature("Domain↔row converters")
class TestSceneConverter:
    @allure.story("Round-trip")
    @allure.title("Scene round-trips preserving SceneNPC role/uuid pairs via to_dict serialization")
    def test_round_trip(self):
        original = scene.Scene(
            location_id=make_uuid("loc-1"),
            description="A quiet square",
            npcs_present=[scene.SceneNPC(role="guard", uuid=make_uuid("npc-1"))],
            points_of_interest=["well"],
            ambient_description="Birds chirp",
            time_of_day="dawn",
        )
        original.narrated_text = "You stand in a quiet square at dawn."

        row = sc_conv.scene_to_row(original, GAME_STATE_ID, is_current=True, scene_number=3)
        assert row["game_state_id"] == GAME_STATE_ID
        assert row["is_current"] is True
        assert row["scene_number"] == 3
        assert row["npcs_present"] == [{"role": "guard", "uuid": str(make_uuid("npc-1"))}]
        # points_of_interest dumped with mode="json": each POI's UUID is a plain str, not a UUID.
        assert isinstance(row["points_of_interest"][0]["uuid"], str)
        assert row["points_of_interest"][0]["names"] == ["well"]

        restored = sc_conv.row_to_scene(row)
        assert restored.uuid == original.uuid
        assert restored.location_id == make_uuid("loc-1")
        assert restored.description == "A quiet square"
        assert len(restored.npcs_present) == 1
        assert restored.npcs_present[0].role == "guard"
        assert restored.npcs_present[0].uuid == make_uuid("npc-1")
        assert [poi.primary_name for poi in restored.points_of_interest] == ["well"]
        assert restored.ambient_description == "Birds chirp"
        assert restored.time_of_day == "dawn"
        assert restored.narrated_text == "You stand in a quiet square at dawn."

    @allure.story("Backwards compatibility")
    @allure.title("row_to_scene handles legacy rows where npcs_present entries are bare UUID strings")
    def test_legacy_string_npcs_present(self):
        original = scene.Scene(location_id=make_uuid("loc-1"))
        row = sc_conv.scene_to_row(original, GAME_STATE_ID)
        # Default-arg contract: an unflagged scene is not current and carries scene number 0.
        assert row["is_current"] is False
        assert row["scene_number"] == 0
        legacy_uuid_str = str(make_uuid("npc-legacy-uuid"))
        row["npcs_present"] = [legacy_uuid_str]

        restored = sc_conv.row_to_scene(row)
        assert len(restored.npcs_present) == 1
        assert restored.npcs_present[0].role == legacy_uuid_str
        assert restored.npcs_present[0].uuid == make_uuid("npc-legacy-uuid")


@allure.epic("Persistence")
@allure.feature("Domain↔row converters")
class TestKnowledgeConverter:
    @allure.story("Round-trip")
    @allure.title("KnowledgeNode round-trips preserving scope, source, canon, education, and salience")
    def test_round_trip(self):
        node = KnowledgeNode(
            text="The king was poisoned",
            scope=KnowledgeScope.COUNTRY,
            source=KnowledgeSource.RUMOR,
            canon=CanonSource.SESSION,
            required_education=5,
            tags=["politics", "scandal"],
            location_id=make_uuid("loc-court"),
            timestamp=12.5,
            salience=0.85,
        )
        row = kn_conv.knowledge_node_to_row(node, GAME_STATE_ID)
        assert row["game_state_id"] == GAME_STATE_ID
        assert row["canon"] == "session"
        assert row["salience"] == pytest.approx(0.85)
        # The scope column is stored lowercased (rehydration re-uppercases it before lookup).
        assert row["scope"] == "country"

        restored = kn_conv.row_to_knowledge_node(row)
        assert restored.uuid == node.uuid
        assert restored.text == "The king was poisoned"
        assert restored.scope == KnowledgeScope.COUNTRY
        assert restored.source == KnowledgeSource.RUMOR
        assert restored.canon == CanonSource.SESSION
        assert restored.required_education == 5
        assert restored.tags == ["politics", "scandal"]
        assert restored.location_id == make_uuid("loc-court")
        assert restored.timestamp == pytest.approx(12.5)
        assert restored.salience == pytest.approx(0.85)

    @allure.story("Backwards compatibility")
    @allure.title("row_to_knowledge_node defaults canon to HISTORICAL on legacy rows missing the column")
    def test_canon_defaults_on_legacy_row(self):
        node = KnowledgeNode(text="Legacy fact")
        row = kn_conv.knowledge_node_to_row(node, GAME_STATE_ID)
        row.pop("canon")

        restored = kn_conv.row_to_knowledge_node(row)
        assert restored.canon == CanonSource.HISTORICAL

    @allure.story("Backwards compatibility")
    @allure.title("row_to_knowledge_node defaults salience to 0.5 on legacy rows missing the column")
    def test_salience_defaults_on_legacy_row(self):
        node = KnowledgeNode(text="Legacy fact")
        row = kn_conv.knowledge_node_to_row(node, GAME_STATE_ID)
        row.pop("salience")

        restored = kn_conv.row_to_knowledge_node(row)
        assert restored.salience == pytest.approx(0.5)


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
            owner_id=make_uuid("npc-1"),
            location_id=make_uuid("loc-1"),
            scope="city",
            effects=[effect],
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
        assert restored.owner_id == make_uuid("npc-1")
        assert restored.location_id == make_uuid("loc-1")
        # A non-default scope must survive rehydration (the default would be "local").
        assert restored.scope == "city"
        assert restored.status == timeline_event.EventStatus.COMPLETED
        assert len(restored.effects) == 1
        assert restored.effects[0].effect_type == "MOVE_NPC"
        assert restored.effects[0].target_id == "npc-1"
        assert restored.effects[0].effect_data == {"npc_id": "npc-1", "to_location_id": "loc-2"}
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

    @allure.story("Round-trip")
    @allure.title("row_to_game_event reads the stored completes_at instead of recomputing it")
    def test_completes_at_read_not_recomputed(self):
        event_obj = timeline_event.GameEvent(name="late", scheduled_at=10, duration=2)
        # Stored completion deliberately diverges from scheduled_at + duration (=12).
        event_obj.completes_at = 99
        row = ev_conv.game_event_to_row(event_obj, GAME_STATE_ID)
        assert row["completes_at"] == pytest.approx(99)

        restored = ev_conv.row_to_game_event(row)
        assert restored.completes_at == pytest.approx(99)

    @allure.story("Backwards compatibility")
    @allure.title("row_to_game_event defaults effect_data to {} when neither effect_data nor params exist")
    def test_effect_data_defaults_to_empty_dict(self):
        event_obj = timeline_event.GameEvent(
            name="bare-effect",
            scheduled_at=0,
            duration=1,
            effects=[timeline_event.EventEffect(effect_type="REST", target_id="npc-1", effect_data={})],
        )
        row = ev_conv.game_event_to_row(event_obj, GAME_STATE_ID)
        # Legacy row whose effect carries neither "effect_data" nor "params".
        row["effects"] = [{"effect_type": "REST", "target_id": "npc-1"}]

        restored = ev_conv.row_to_game_event(row)
        assert restored.effects[0].effect_data == {}
