"""Tests for :func:`cast.visible_entities.collect_visible_entities`."""

from __future__ import annotations

from uuid import UUID

import allure

from cast.visible_entities import collect_visible_entities
from knowledge.graph import KnowledgeGraph
from models import game_state as _gs, location as _loc, npc_card as _npc, scene as _scene, setting as _setting
from tests._log_helpers import capture_warnings
from tests._uuid_helpers import make_uuid

_NPC_1 = make_uuid("npc-1")
_NPC_MISSING = make_uuid("npc-missing")
_TAVERN = make_uuid("tavern")

GameState = _gs.GameState
Location = _loc.Location
NPCCard = _npc.NPCCard
PointOfInterest = _scene.PointOfInterest
Scene = _scene.Scene
SceneNPC = _scene.SceneNPC
Setting = _setting.Setting


def _make_state() -> GameState:
    setting = Setting(name="Test", time_period="now", region="nowhere", summary="")
    return GameState(setting=setting, knowledge_graph=KnowledgeGraph())


def _register_npc(
    gs: GameState,
    uuid: UUID,
    name: str = "Tony",
    occupation: str = "watchman",
    short_descriptor: str = "an armed man",
) -> NPCCard:
    npc = NPCCard(name=name, occupation=occupation, short_descriptor=short_descriptor)
    npc.uuid = uuid
    gs.npcs[uuid] = npc
    return npc


@allure.epic("Narrator & UI")
@allure.feature("Visible entities collector")
class TestCollectVisibleEntities:
    @allure.story("Unknown NPC")
    @allure.title("Unknown NPCs render under their short_descriptor, not the canonical name")
    def test_unknown_npc(self):
        gs = _make_state()
        _register_npc(gs, _NPC_1)
        scene = Scene(
            location_id=_TAVERN,
            npcs_present=[SceneNPC(role="guard", uuid=_NPC_1)],
        )
        entities = collect_visible_entities(scene, gs, None)
        assert len(entities) == 1
        entity = entities[0]
        assert entity.kind == "npc"
        assert entity.id == str(_NPC_1)
        assert entity.names == ["an armed man", "guard"]

    @allure.story("Introduced NPC")
    @allure.title("Introduced NPCs expose the combined label plus the bare name and occupation alias")
    def test_introduced_npc(self):
        gs = _make_state()
        _register_npc(gs, _NPC_1)
        gs.player.known_npcs.add(_NPC_1)
        scene = Scene(
            location_id=_TAVERN,
            npcs_present=[SceneNPC(role="guard", uuid=_NPC_1)],
        )
        entity = collect_visible_entities(scene, gs, None)[0]
        assert entity.names == ["Tony (watchman)", "Tony", "the watchman", "guard"]

    @allure.story("Points of interest")
    @allure.title("Typed POIs surface with their alias lists intact, tagged as 'poi'")
    def test_poi_entities(self):
        gs = _make_state()
        hearth = PointOfInterest(names=["fireplace", "the hearth"])
        scene = Scene(
            location_id=_TAVERN,
            points_of_interest=[hearth],
        )
        entity = collect_visible_entities(scene, gs, None)[0]
        assert entity.kind == "poi"
        assert entity.id == str(hearth.uuid)
        assert entity.names == ["fireplace", "the hearth"]

    @allure.story("Tracked items")
    @allure.title("Location.object_states keys not already covered by POI aliases surface as items")
    def test_items_from_object_states(self):
        gs = _make_state()
        scene = Scene(location_id=_TAVERN)
        location = Location(
            name="Tavern",
            object_states={"shutter": "splintered", "bar": "polished"},
        )
        entities = collect_visible_entities(scene, gs, location)
        assert {entity.id for entity in entities} == {"shutter", "bar"}
        assert all(entity.kind == "item" for entity in entities)

    @allure.story("Tracked items")
    @allure.title("An object_states key is suppressed when a POI alias already contains it")
    def test_item_suppressed_by_poi_overlap(self):
        gs = _make_state()
        scene = Scene(
            location_id=_TAVERN,
            points_of_interest=[PointOfInterest(names=["broken shutter"])],
        )
        location = Location(name="Tavern", object_states={"shutter": "splintered"})
        entities = collect_visible_entities(scene, gs, location)
        kinds = {entity.kind for entity in entities}
        assert kinds == {"poi"}

    @allure.story("Empty scene")
    @allure.title("A None scene yields no entities and never raises")
    def test_none_scene(self):
        gs = _make_state()
        assert collect_visible_entities(None, gs, None) == []

    @allure.story("Tracked items")
    @allure.title("Token-boundary suppression: a short item key is NOT swallowed by a longer POI alias containing it")
    def test_item_short_key_not_swallowed_by_substring(self):
        gs = _make_state()
        scene = Scene(
            location_id=_TAVERN,
            points_of_interest=[PointOfInterest(names=["bar"])],
        )
        location = Location(name="Tavern", object_states={"ar": "etched"})
        entities = collect_visible_entities(scene, gs, location)
        item_ids = {entity.id for entity in entities if entity.kind == "item"}
        assert "ar" in item_ids

    @allure.story("Invariant logging")
    @allure.title("A SceneNPC with a uuid but no NPCCard registered logs a warning and is skipped")
    def test_missing_npc_card_logs_warning(self):
        gs = _make_state()
        scene = Scene(
            location_id=_TAVERN,
            npcs_present=[SceneNPC(role="guard", uuid=_NPC_MISSING)],
        )
        with capture_warnings() as messages:
            entities = collect_visible_entities(scene, gs, None)
        assert entities == []
        assert any(str(_NPC_MISSING) in message for message in messages)

    @allure.story("Invariant logging")
    @allure.title("A SceneNPC without a uuid is skipped silently (pre-init state is expected)")
    def test_scene_npc_without_uuid_skipped_silently(self):
        gs = _make_state()
        scene = Scene(
            location_id=_TAVERN,
            npcs_present=[SceneNPC(role="guard")],
        )
        with capture_warnings() as messages:
            entities = collect_visible_entities(scene, gs, None)
        assert entities == []
        assert not any("visible_entities" in message for message in messages)
