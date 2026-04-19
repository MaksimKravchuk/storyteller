"""Tests for :func:`cast.visible_entities.collect_visible_entities`."""

from __future__ import annotations

import allure

from cast.visible_entities import collect_visible_entities
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.location import Location
from models.npc_card import NPCCard
from models.scene import PointOfInterest, Scene, SceneNPC
from models.setting import Setting


def _make_state() -> GameState:
    setting = Setting(name="Test", time_period="now", region="nowhere", summary="")
    return GameState(setting=setting, knowledge_graph=KnowledgeGraph())


def _register_npc(
    gs: GameState,
    uuid: str,
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
        _register_npc(gs, "npc-1")
        scene = Scene(
            location_id="tavern",
            npcs_present=[SceneNPC(role="guard", uuid="npc-1")],
        )
        entities = collect_visible_entities(scene, gs, None)
        assert len(entities) == 1
        entity = entities[0]
        assert entity.kind == "npc"
        assert entity.id == "npc-1"
        assert entity.names == ["an armed man"]

    @allure.story("Introduced NPC")
    @allure.title("Introduced NPCs expose the combined label plus the bare name and occupation alias")
    def test_introduced_npc(self):
        gs = _make_state()
        _register_npc(gs, "npc-1")
        gs.player.known_npcs.add("npc-1")
        scene = Scene(
            location_id="tavern",
            npcs_present=[SceneNPC(role="guard", uuid="npc-1")],
        )
        entity = collect_visible_entities(scene, gs, None)[0]
        assert entity.names == ["Tony (watchman)", "Tony", "the watchman"]

    @allure.story("Points of interest")
    @allure.title("Typed POIs surface with their alias lists intact, tagged as 'poi'")
    def test_poi_entities(self):
        gs = _make_state()
        hearth = PointOfInterest(names=["fireplace", "the hearth"])
        scene = Scene(
            location_id="tavern",
            points_of_interest=[hearth],
        )
        entity = collect_visible_entities(scene, gs, None)[0]
        assert entity.kind == "poi"
        assert entity.id == hearth.uuid
        assert entity.names == ["fireplace", "the hearth"]

    @allure.story("Tracked items")
    @allure.title("Location.object_states keys not already covered by POI aliases surface as items")
    def test_items_from_object_states(self):
        gs = _make_state()
        scene = Scene(location_id="tavern")
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
            location_id="tavern",
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
