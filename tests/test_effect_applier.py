"""Tests for EffectApplier across every supported effect type."""

from __future__ import annotations

import allure

from knowledge.graph import KnowledgeGraph
from knowledge.node import CanonSource, KnowledgeScope, KnowledgeSource
from models.game_state import GameState
from models.location import Location
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from models.setting import Setting
from tests._uuid_helpers import make_uuid
from timeline.effect_applier import EffectApplier
from timeline.event import EventEffect

_LOC_1 = make_uuid("loc-1")
_LOC_2 = make_uuid("loc-2")


def _make_game_state_with_npc(npc: NPCCard) -> GameState:
    gs = GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=KnowledgeGraph(),
    )
    gs.npcs[npc.uuid] = npc
    return gs


def _empty_game_state() -> GameState:
    return GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=KnowledgeGraph(),
    )


@allure.epic("Game Timeline")
@allure.feature("Effect application")
class TestChangeStatusEffect:
    @allure.story("Change status")
    @allure.title("CHANGE_STATUS effect updates the target NPC's physical_status field in place")
    def test_changes_physical_status(self):
        npc = NPCCard(name="Guard", occupation="guard", physical_status="wounded")
        gs = _make_game_state_with_npc(npc)
        applier = EffectApplier(gs, KnowledgeGraph())

        effect = EventEffect(
            effect_type="CHANGE_STATUS",
            target_id=npc.uuid,
            effect_data={"npc_id": npc.uuid, "status": "healthy"},
        )
        applier.apply(effect)
        assert npc.physical_status == "healthy"

    @allure.story("No-op on missing target")
    @allure.title("CHANGE_STATUS effect targeting an unknown NPC UUID is silently ignored without raising")
    def test_noop_when_npc_not_found(self):
        npc = NPCCard(name="Guard", occupation="guard")
        gs = _make_game_state_with_npc(npc)
        applier = EffectApplier(gs, KnowledgeGraph())

        effect = EventEffect(
            effect_type="CHANGE_STATUS",
            target_id=str(make_uuid("nonexistent-uuid")),
            effect_data={"npc_id": str(make_uuid("nonexistent-uuid")), "status": "wounded"},
        )
        # Should not raise
        applier.apply(effect)
        assert npc.physical_status == "healthy"

    @allure.story("Change status")
    @allure.title("CHANGE_STATUS effect accepts free-form multi-word status strings like 'wounded left arm'")
    def test_sets_multi_word_status(self):
        npc = NPCCard(name="Guard", occupation="guard")
        gs = _make_game_state_with_npc(npc)
        applier = EffectApplier(gs, KnowledgeGraph())

        effect = EventEffect(
            effect_type="CHANGE_STATUS",
            target_id=npc.uuid,
            effect_data={"npc_id": npc.uuid, "status": "wounded left arm"},
        )
        applier.apply(effect)
        assert npc.physical_status == "wounded left arm"


@allure.epic("Game Timeline")
@allure.feature("Effect application")
class TestMoveNpcEffect:
    @allure.story("Move NPC")
    @allure.title("MOVE_NPC removes the NPC from the old location and adds them to the new one")
    def test_moves_between_locations(self):
        npc = NPCCard(name="Marcus", occupation="guard", location_id=_LOC_1)
        gs = _make_game_state_with_npc(npc)
        gs.locations[_LOC_1] = Location(name="Gate")
        gs.locations[_LOC_1].npcs_present.append(npc.uuid)
        gs.locations[_LOC_2] = Location(name="Forum")

        effect = EventEffect(
            effect_type="MOVE_NPC",
            target_id=npc.uuid,
            effect_data={"npc_id": npc.uuid, "to_location_id": str(_LOC_2)},
        )
        EffectApplier(gs, KnowledgeGraph()).apply(effect)

        assert npc.location_id == _LOC_2
        assert npc.uuid not in gs.locations[_LOC_1].npcs_present
        assert npc.uuid in gs.locations[_LOC_2].npcs_present

    @allure.story("Move NPC")
    @allure.title("MOVE_NPC into the current scene's location adds the NPC to scene.npcs_present")
    def test_adds_npc_to_current_scene_on_arrival(self):
        npc = NPCCard(name="Marcus", occupation="guard", location_id=_LOC_1)
        gs = _make_game_state_with_npc(npc)
        gs.locations[_LOC_1] = Location(name="Gate")
        gs.locations[_LOC_2] = Location(name="Forum")
        gs.current_scene = Scene(location_id=_LOC_2)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(
                effect_type="MOVE_NPC",
                target_id=npc.uuid,
                effect_data={"npc_id": npc.uuid, "to_location_id": str(_LOC_2)},
            )
        )

        assert any(snpc.uuid == npc.uuid for snpc in gs.current_scene.npcs_present)

    @allure.story("Move NPC")
    @allure.title("MOVE_NPC does not duplicate a scene NPC entry when the NPC is already present")
    def test_does_not_duplicate_scene_npc(self):
        npc = NPCCard(name="Marcus", occupation="guard", location_id=_LOC_1)
        gs = _make_game_state_with_npc(npc)
        gs.locations[_LOC_1] = Location(name="Gate")
        gs.locations[_LOC_2] = Location(name="Forum")
        gs.current_scene = Scene(
            location_id=_LOC_2,
            npcs_present=[SceneNPC(role="guard", uuid=npc.uuid)],
        )

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(
                effect_type="MOVE_NPC",
                target_id=npc.uuid,
                effect_data={"npc_id": npc.uuid, "to_location_id": str(_LOC_2)},
            )
        )

        assert sum(1 for snpc in gs.current_scene.npcs_present if snpc.uuid == npc.uuid) == 1

    @allure.story("Move NPC")
    @allure.title("MOVE_NPC is silently ignored when the target NPC does not exist")
    def test_noop_on_missing_npc(self):
        gs = _empty_game_state()

        # Should not raise even though the NPC is not in game_state.
        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(
                effect_type="MOVE_NPC",
                target_id=str(make_uuid("ghost")),
                effect_data={"npc_id": str(make_uuid("ghost")), "to_location_id": str(_LOC_2)},
            )
        )


@allure.epic("Game Timeline")
@allure.feature("Effect application")
class TestItemEffects:
    @allure.story("Add item")
    @allure.title("ADD_ITEM appends the item to the target NPC's inventory")
    def test_add_item(self):
        npc = NPCCard(name="Marcus", occupation="guard")
        gs = _make_game_state_with_npc(npc)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(
                effect_type="ADD_ITEM",
                target_id=npc.uuid,
                effect_data={"npc_id": npc.uuid, "item": "sword"},
            )
        )
        assert "sword" in npc.inventory

    @allure.story("Add item")
    @allure.title("ADD_ITEM is a no-op when the item string is empty")
    def test_add_item_empty_item_is_noop(self):
        npc = NPCCard(name="Marcus", occupation="guard")
        gs = _make_game_state_with_npc(npc)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(
                effect_type="ADD_ITEM",
                target_id=npc.uuid,
                effect_data={"npc_id": npc.uuid, "item": ""},
            )
        )
        assert npc.inventory == []

    @allure.story("Remove item")
    @allure.title("REMOVE_ITEM drops an existing item from the NPC's inventory")
    def test_remove_item(self):
        npc = NPCCard(name="Marcus", occupation="guard", inventory=["sword"])
        gs = _make_game_state_with_npc(npc)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(
                effect_type="REMOVE_ITEM",
                target_id=npc.uuid,
                effect_data={"npc_id": npc.uuid, "item": "sword"},
            )
        )
        assert "sword" not in npc.inventory

    @allure.story("Remove item")
    @allure.title("REMOVE_ITEM silently ignores items the NPC does not currently hold")
    def test_remove_item_absent_is_noop(self):
        npc = NPCCard(name="Marcus", occupation="guard", inventory=["shield"])
        gs = _make_game_state_with_npc(npc)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(
                effect_type="REMOVE_ITEM",
                target_id=npc.uuid,
                effect_data={"npc_id": npc.uuid, "item": "sword"},
            )
        )
        assert npc.inventory == ["shield"]


@allure.epic("Game Timeline")
@allure.feature("Effect application")
class TestAddKnowledgeEffect:
    @allure.story("Add knowledge")
    @allure.title("ADD_KNOWLEDGE inserts a FACT KnowledgeNode into the graph with scope/tags/location")
    def test_adds_node_with_scope_and_tags(self):
        gs = _empty_game_state()
        graph = KnowledgeGraph()

        EffectApplier(gs, graph).apply(
            EventEffect(
                effect_type="ADD_KNOWLEDGE",
                target_id="",
                effect_data={
                    "content": "The bridge has collapsed",
                    "scope": "city",
                    "tags": ["news"],
                    "location_id": str(_LOC_1),
                },
            )
        )

        nodes = graph.all_nodes()
        assert len(nodes) == 1
        assert nodes[0].text == "The bridge has collapsed"
        assert nodes[0].scope == KnowledgeScope.CITY
        assert nodes[0].source == KnowledgeSource.FACT
        assert nodes[0].canon == CanonSource.SESSION
        assert nodes[0].tags == ["news"]
        assert nodes[0].location_id == _LOC_1

    @allure.story("Add knowledge")
    @allure.title("ADD_KNOWLEDGE defaults to LOCAL scope when 'scope' is omitted")
    def test_defaults_to_local_scope(self):
        graph = KnowledgeGraph()
        EffectApplier(_empty_game_state(), graph).apply(
            EventEffect(
                effect_type="ADD_KNOWLEDGE",
                target_id="",
                effect_data={"content": "A rumor"},
            )
        )
        assert graph.all_nodes()[0].scope == KnowledgeScope.LOCAL

    @allure.story("Add knowledge")
    @allure.title("ADD_KNOWLEDGE is a no-op when content is empty")
    def test_empty_content_is_noop(self):
        graph = KnowledgeGraph()
        EffectApplier(_empty_game_state(), graph).apply(
            EventEffect(
                effect_type="ADD_KNOWLEDGE",
                target_id="",
                effect_data={"content": ""},
            )
        )
        assert graph.all_nodes() == []

    @allure.story("Add knowledge")
    @allure.title("ADD_KNOWLEDGE writes nothing when the content key is absent entirely")
    def test_missing_content_key_is_noop(self):
        graph = KnowledgeGraph()
        EffectApplier(_empty_game_state(), graph).apply(
            EventEffect(effect_type="ADD_KNOWLEDGE", target_id="", effect_data={"scope": "city"})
        )
        assert graph.all_nodes() == []


@allure.epic("Game Timeline")
@allure.feature("Effect application")
class TestChangeAttributeEffect:
    @allure.story("Change attribute")
    @allure.title("CHANGE_ATTRIBUTE updates an NPC's attribute dict in place")
    def test_updates_attribute(self):
        npc = NPCCard(name="Marcus", occupation="guard", attributes={"strength": 5})
        gs = _make_game_state_with_npc(npc)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(
                effect_type="CHANGE_ATTRIBUTE",
                target_id=npc.uuid,
                effect_data={"attribute": "strength", "value": 8},
            )
        )
        assert npc.attributes["strength"] == 8

    @allure.story("Change attribute")
    @allure.title("CHANGE_ATTRIBUTE is a no-op when attribute name is empty")
    def test_empty_attribute_is_noop(self):
        npc = NPCCard(name="Marcus", occupation="guard", attributes={"strength": 5})
        gs = _make_game_state_with_npc(npc)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(
                effect_type="CHANGE_ATTRIBUTE",
                target_id=npc.uuid,
                effect_data={"attribute": "", "value": 99},
            )
        )
        assert npc.attributes == {"strength": 5}


@allure.epic("Game Timeline")
@allure.feature("Effect application")
class TestRemoveNpcEffect:
    @allure.story("Remove NPC")
    @allure.title("REMOVE_NPC drops the NPC from game_state, its location, and the current scene")
    def test_removes_npc_fully(self):
        npc = NPCCard(name="Marcus", occupation="guard", location_id=_LOC_1)
        gs = _make_game_state_with_npc(npc)
        gs.locations[_LOC_1] = Location(name="Gate")
        gs.locations[_LOC_1].npcs_present.append(npc.uuid)
        gs.current_scene = Scene(
            location_id=_LOC_1,
            npcs_present=[SceneNPC(role="guard", uuid=npc.uuid)],
        )

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(effect_type="REMOVE_NPC", target_id=npc.uuid, effect_data={}),
        )

        assert npc.uuid not in gs.npcs
        assert npc.uuid not in gs.locations[_LOC_1].npcs_present
        assert all(snpc.uuid != npc.uuid for snpc in gs.current_scene.npcs_present)

    @allure.story("Remove NPC")
    @allure.title("REMOVE_NPC targeting an unknown NPC is a silent no-op")
    def test_noop_on_missing_npc(self):
        gs = _empty_game_state()

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(effect_type="REMOVE_NPC", target_id=str(make_uuid("ghost")), effect_data={}),
        )


@allure.epic("Game Timeline")
@allure.feature("Effect application")
class TestUnknownEffect:
    @allure.story("Unknown effect type")
    @allure.title("Unknown effect types like SPAWN_NPC are silently skipped by the applier")
    def test_unknown_effect_is_skipped(self):
        gs = _empty_game_state()

        # SPAWN_NPC is handled by Director, not EffectApplier — it must not raise.
        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(effect_type="SPAWN_NPC", target_id="", effect_data={"npc_request": "merchant"}),
        )


_OTHER_ID = make_uuid("some-other-id")


@allure.epic("Game Timeline")
@allure.feature("Effect application")
class TestNpcIdResolution:
    """The npc_id effect_data key takes priority; target_id is only the fallback.

    Tests where target_id == npc_id cannot tell the two apart — these pin
    the resolution by making them differ, and by omitting npc_id entirely.
    """

    @allure.story("npc_id resolution")
    @allure.title("ADD_ITEM applies to the npc_id NPC even when target_id points elsewhere")
    def test_add_item_prefers_npc_id_over_target_id(self):
        npc = NPCCard(name="Marcus", occupation="guard")
        gs = _make_game_state_with_npc(npc)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(
                effect_type="ADD_ITEM",
                target_id=str(_OTHER_ID),
                effect_data={"npc_id": str(npc.uuid), "item": "sword"},
            )
        )
        assert npc.inventory == ["sword"]

    @allure.story("npc_id resolution")
    @allure.title("ADD_ITEM falls back to target_id when no npc_id key is present")
    def test_add_item_falls_back_to_target_id(self):
        npc = NPCCard(name="Marcus", occupation="guard")
        gs = _make_game_state_with_npc(npc)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(effect_type="ADD_ITEM", target_id=str(npc.uuid), effect_data={"item": "sword"})
        )
        assert npc.inventory == ["sword"]

    @allure.story("npc_id resolution")
    @allure.title("ADD_ITEM with no item key is a no-op (the absent-item default is falsy)")
    def test_add_item_missing_item_key_is_noop(self):
        npc = NPCCard(name="Marcus", occupation="guard")
        gs = _make_game_state_with_npc(npc)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(effect_type="ADD_ITEM", target_id=str(npc.uuid), effect_data={"npc_id": str(npc.uuid)})
        )
        assert npc.inventory == []

    @allure.story("npc_id resolution")
    @allure.title("REMOVE_ITEM applies to the npc_id NPC even when target_id points elsewhere")
    def test_remove_item_prefers_npc_id_over_target_id(self):
        npc = NPCCard(name="Marcus", occupation="guard", inventory=["sword"])
        gs = _make_game_state_with_npc(npc)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(
                effect_type="REMOVE_ITEM",
                target_id=str(_OTHER_ID),
                effect_data={"npc_id": str(npc.uuid), "item": "sword"},
            )
        )
        assert npc.inventory == []

    @allure.story("npc_id resolution")
    @allure.title("REMOVE_ITEM falls back to target_id when no npc_id key is present")
    def test_remove_item_falls_back_to_target_id(self):
        npc = NPCCard(name="Marcus", occupation="guard", inventory=["sword"])
        gs = _make_game_state_with_npc(npc)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(effect_type="REMOVE_ITEM", target_id=str(npc.uuid), effect_data={"item": "sword"})
        )
        assert npc.inventory == []

    @allure.story("npc_id resolution")
    @allure.title("CHANGE_STATUS applies to the npc_id NPC even when target_id points elsewhere")
    def test_change_status_prefers_npc_id_over_target_id(self):
        npc = NPCCard(name="Guard", occupation="guard", physical_status="healthy")
        gs = _make_game_state_with_npc(npc)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(
                effect_type="CHANGE_STATUS",
                target_id=str(_OTHER_ID),
                effect_data={"npc_id": str(npc.uuid), "status": "wounded"},
            )
        )
        assert npc.physical_status == "wounded"

    @allure.story("npc_id resolution")
    @allure.title("CHANGE_STATUS falls back to target_id when no npc_id key is present")
    def test_change_status_falls_back_to_target_id(self):
        npc = NPCCard(name="Guard", occupation="guard", physical_status="healthy")
        gs = _make_game_state_with_npc(npc)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(effect_type="CHANGE_STATUS", target_id=str(npc.uuid), effect_data={"status": "wounded"})
        )
        assert npc.physical_status == "wounded"

    @allure.story("npc_id resolution")
    @allure.title("CHANGE_STATUS with no status key leaves the NPC's status untouched")
    def test_change_status_missing_status_key_is_noop(self):
        npc = NPCCard(name="Guard", occupation="guard", physical_status="healthy")
        gs = _make_game_state_with_npc(npc)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(effect_type="CHANGE_STATUS", target_id=str(npc.uuid), effect_data={"npc_id": str(npc.uuid)})
        )
        assert npc.physical_status == "healthy"

    @allure.story("npc_id resolution")
    @allure.title("MOVE_NPC moves the npc_id NPC even when target_id points elsewhere")
    def test_move_npc_prefers_npc_id_over_target_id(self):
        npc = NPCCard(name="Marcus", occupation="guard", location_id=_LOC_1)
        gs = _make_game_state_with_npc(npc)
        gs.locations[_LOC_1] = Location(name="Gate")
        gs.locations[_LOC_2] = Location(name="Forum")

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(
                effect_type="MOVE_NPC",
                target_id=str(_OTHER_ID),
                effect_data={"npc_id": str(npc.uuid), "to_location_id": str(_LOC_2)},
            )
        )
        assert npc.location_id == _LOC_2

    @allure.story("npc_id resolution")
    @allure.title("MOVE_NPC falls back to target_id when no npc_id key is present")
    def test_move_npc_falls_back_to_target_id(self):
        npc = NPCCard(name="Marcus", occupation="guard", location_id=_LOC_1)
        gs = _make_game_state_with_npc(npc)
        gs.locations[_LOC_1] = Location(name="Gate")
        gs.locations[_LOC_2] = Location(name="Forum")

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(
                effect_type="MOVE_NPC",
                target_id=str(npc.uuid),
                effect_data={"to_location_id": str(_LOC_2)},
            )
        )
        assert npc.location_id == _LOC_2


@allure.epic("Game Timeline")
@allure.feature("Effect application")
class TestChangeAttributeDefaults:
    @allure.story("Attribute defaults")
    @allure.title("CHANGE_ATTRIBUTE with no value key writes the numeric default of 0")
    def test_missing_value_defaults_to_zero(self):
        npc = NPCCard(name="Marcus", occupation="guard", attributes={"strength": 5})
        gs = _make_game_state_with_npc(npc)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(effect_type="CHANGE_ATTRIBUTE", target_id=str(npc.uuid), effect_data={"attribute": "strength"})
        )
        assert npc.attributes["strength"] == 0

    @allure.story("Attribute defaults")
    @allure.title("CHANGE_ATTRIBUTE with no attribute key is a no-op")
    def test_missing_attribute_key_is_noop(self):
        npc = NPCCard(name="Marcus", occupation="guard", attributes={"strength": 5})
        gs = _make_game_state_with_npc(npc)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(effect_type="CHANGE_ATTRIBUTE", target_id=str(npc.uuid), effect_data={"value": 9})
        )
        assert npc.attributes == {"strength": 5}


@allure.epic("Game Timeline")
@allure.feature("Effect application")
class TestMoveAndRemoveLocationGuards:
    @allure.story("Stale location")
    @allure.title("MOVE_NPC tolerates an NPC whose current location is no longer registered")
    def test_move_npc_with_stale_origin_does_not_raise(self):
        # npc.location_id (_LOC_2) is NOT in gs.locations — the `is not None AND in locations`
        # guard must short-circuit on the membership half rather than index a missing key.
        npc = NPCCard(name="Marcus", occupation="guard", location_id=_LOC_2)
        gs = _make_game_state_with_npc(npc)
        gs.locations[_LOC_1] = Location(name="Gate")

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(
                effect_type="MOVE_NPC",
                target_id=str(npc.uuid),
                effect_data={"npc_id": str(npc.uuid), "to_location_id": str(_LOC_1)},
            )
        )
        assert npc.location_id == _LOC_1
        assert npc.uuid in gs.locations[_LOC_1].npcs_present

    @allure.story("Scene role")
    @allure.title("MOVE_NPC into the scene labels the arrival with the NPC's occupation, not their name")
    def test_arrival_scene_role_is_occupation(self):
        npc = NPCCard(name="Marcus", occupation="guard", location_id=_LOC_1)
        gs = _make_game_state_with_npc(npc)
        gs.locations[_LOC_1] = Location(name="Gate")
        gs.locations[_LOC_2] = Location(name="Forum")
        gs.current_scene = Scene(location_id=_LOC_2)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(
                effect_type="MOVE_NPC",
                target_id=str(npc.uuid),
                effect_data={"npc_id": str(npc.uuid), "to_location_id": str(_LOC_2)},
            )
        )
        arrival = next(snpc for snpc in gs.current_scene.npcs_present if snpc.uuid == npc.uuid)
        assert arrival.role == "guard"

    @allure.story("Stale location")
    @allure.title("REMOVE_NPC tolerates an NPC whose current location is no longer registered")
    def test_remove_npc_with_stale_location_does_not_raise(self):
        npc = NPCCard(name="Marcus", occupation="guard", location_id=_LOC_2)
        gs = _make_game_state_with_npc(npc)
        gs.locations[_LOC_1] = Location(name="Gate")

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(effect_type="REMOVE_NPC", target_id=str(npc.uuid), effect_data={}),
        )
        assert npc.uuid not in gs.npcs


def _state_with_location(loc_id) -> GameState:
    gs = _empty_game_state()
    gs.locations[loc_id] = Location(name="Workshop")
    return gs


@allure.epic("Game Timeline")
@allure.feature("Effect application")
class TestObjectDamageResolution:
    @allure.story("Object damage")
    @allure.title("APPLY_OBJECT_DAMAGE uses the location_id key over target_id when both are present")
    def test_prefers_location_id_key_over_target_id(self):
        gs = _state_with_location(_LOC_1)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(
                effect_type="APPLY_OBJECT_DAMAGE",
                target_id=str(_OTHER_ID),
                effect_data={"location_id": str(_LOC_1), "object_key": "window", "state_description": "shattered"},
            )
        )
        assert gs.locations[_LOC_1].object_states == {"window": "shattered"}

    @allure.story("Object damage")
    @allure.title("APPLY_OBJECT_DAMAGE with no object_key records nothing")
    def test_missing_object_key_records_nothing(self):
        gs = _state_with_location(_LOC_1)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(
                effect_type="APPLY_OBJECT_DAMAGE",
                target_id=str(_LOC_1),
                effect_data={"state_description": "shattered"},
            )
        )
        assert gs.locations[_LOC_1].object_states == {}

    @allure.story("Object damage")
    @allure.title("APPLY_OBJECT_DAMAGE with no state_description records nothing")
    def test_missing_state_description_records_nothing(self):
        gs = _state_with_location(_LOC_1)

        EffectApplier(gs, KnowledgeGraph()).apply(
            EventEffect(
                effect_type="APPLY_OBJECT_DAMAGE",
                target_id=str(_LOC_1),
                effect_data={"object_key": "window"},
            )
        )
        assert gs.locations[_LOC_1].object_states == {}
