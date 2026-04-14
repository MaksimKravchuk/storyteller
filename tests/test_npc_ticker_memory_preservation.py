"""Integration tests for KER-9: NPCTicker must preserve departing NPC memories.

These tests drive the full :meth:`cast.npc_ticker.NPCTicker.tick` path
and assert that session-canon memories witnessed by an evicted NPC
are propagated as hearsay to same-city non-witnesses via
:func:`knowledge.memory_preservation.preserve_departing_npc_memories`.
The pure function is unit-tested in
``tests/test_memory_preservation.py``; this file exercises the wiring.
"""

from __future__ import annotations

import allure

from cast.npc_ticker import NPCTicker
from cast.schemas.turn_outputs import TurnOutputs
from knowledge.graph import KnowledgeGraph
from knowledge.node import (
    CanonSource,
    EdgeType,
    KnowledgeNode,
    KnowledgeScope,
    KnowledgeSource,
)
from knowledge.query import KnowledgeQueryEngine
from models.game_state import GameState
from models.location import Location
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from models.setting import Setting

pytestmark = [
    allure.epic("NPC Interaction"),
    allure.feature("NPC schedule ticker"),
]

_CITY_ID = "loc-city-rome"
_TAVERN_ID = "loc-tavern"
_MARKET_ID = "loc-market"

_BARTENDER_UUID = "npc-bartender"
_BAKER_UUID = "npc-baker"
_GUARD_UUID = "npc-guard"
_SCHOLAR_UUID = "npc-scholar"

_MEMORY_TEXT = "The player confessed to stealing the senator's ring."


def _make_city_state(game_time: str = "morning") -> GameState:
    """Build a game state with a 2-location Rome city for preservation tests."""
    gs = GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=KnowledgeGraph(),
    )
    gs.game_time = game_time
    gs.locations[_CITY_ID] = Location(
        name="Rome",
        location_type="city",
        parent_location_id=None,
    )
    gs.locations[_TAVERN_ID] = Location(
        name="Tavern",
        location_type="building",
        parent_location_id=_CITY_ID,
        npcs_present=[],
    )
    gs.locations[_MARKET_ID] = Location(
        name="Market",
        location_type="building",
        parent_location_id=_CITY_ID,
        npcs_present=[],
    )
    return gs


def _add_city_npc(
    gs: GameState,
    uuid: str,
    name: str,
    occupation: str,
    location_id: str,
) -> NPCCard:
    """Add an NPC anchored to a specific city-location and register it in the graph."""
    npc = NPCCard(name=name, occupation=occupation, location_id=location_id)
    npc.uuid = uuid
    gs.npcs[uuid] = npc
    gs.locations[location_id].npcs_present.append(uuid)
    gs.knowledge_graph.register_actor_node(uuid, label=name)
    return npc


def _set_scene_at(gs: GameState, location_id: str, *npc_uuids: str) -> Scene:
    scene = Scene(
        location_id=location_id,
        description="The {0}".format(gs.locations[location_id].name),
        npcs_present=[SceneNPC(role="npc", uuid=uid) for uid in npc_uuids],
    )
    gs.current_scene = scene
    return scene


def _add_session_memory(
    gs: GameState,
    npc_id: str,
    text: str = _MEMORY_TEXT,
) -> KnowledgeNode:
    memory = KnowledgeNode(
        text=text,
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.PERSONAL_EXPERIENCE,
        canon=CanonSource.SESSION,
        location_id=_TAVERN_ID,
        timestamp=1.0,
    )
    gs.knowledge_graph.add_node(memory)
    gs.knowledge_graph.add_edge(npc_id, memory.uuid, EdgeType.WITNESSED)
    return memory


def _hearsay_at(gs: GameState, location_id: str) -> list[KnowledgeNode]:
    return [
        node
        for node in gs.knowledge_graph.all_nodes()
        if node.source == KnowledgeSource.HEARSAY and node.location_id == location_id
    ]


@allure.story("Memory preservation")
@allure.title("Evicting a bartender propagates their session memory as hearsay for a same-city baker")
def test_bartender_eviction_creates_hearsay_for_other_city_npcs() -> None:
    gs = _make_city_state(game_time="morning")
    _add_city_npc(gs, _BARTENDER_UUID, "Marco", "bartender", _TAVERN_ID)
    _add_city_npc(gs, _BAKER_UUID, "Bruno", "baker", _MARKET_ID)
    _set_scene_at(gs, _TAVERN_ID, _BARTENDER_UUID)
    _add_session_memory(gs, _BARTENDER_UUID)

    NPCTicker(gs).tick(TurnOutputs())

    hearsay_at_market = _hearsay_at(gs, _MARKET_ID)
    assert len(hearsay_at_market) == 1
    hearsay = hearsay_at_market[0]
    assert hearsay.text == _MEMORY_TEXT
    told_by_edges = [
        (target, edge_attrs)
        for _, target, edge_attrs in gs.knowledge_graph.digraph.out_edges(hearsay.uuid, data=True)
        if edge_attrs.get("edge_type") == EdgeType.TOLD_BY
    ]
    assert len(told_by_edges) == 1
    target_id, edge_attrs = told_by_edges[0]
    assert target_id == _BARTENDER_UUID
    assert edge_attrs.get("recipient_id") == _BAKER_UUID


@allure.story("Memory preservation")
@allure.title("After eviction the departing NPC still keeps their own WITNESSED memory")
def test_bartender_keeps_own_memory_after_departure() -> None:
    gs = _make_city_state(game_time="morning")
    _add_city_npc(gs, _BARTENDER_UUID, "Marco", "bartender", _TAVERN_ID)
    _add_city_npc(gs, _BAKER_UUID, "Bruno", "baker", _MARKET_ID)
    _set_scene_at(gs, _TAVERN_ID, _BARTENDER_UUID)
    memory = _add_session_memory(gs, _BARTENDER_UUID)

    NPCTicker(gs).tick(TurnOutputs())

    engine = KnowledgeQueryEngine(gs.knowledge_graph)
    own_memories = engine.get_memories_about(_BARTENDER_UUID)
    assert any(node.uuid == memory.uuid for node in own_memories)


@allure.story("Memory preservation")
@allure.title("An always-present NPC is never evicted, so no preservation runs and no tag is added")
def test_always_present_npc_never_triggers_preservation() -> None:
    gs = _make_city_state(game_time="morning")
    # Unknown occupation falls back to _ALWAYS_PRESENT so the ticker never evicts.
    _add_city_npc(gs, _SCHOLAR_UUID, "Seneca", "scholar", _TAVERN_ID)
    _add_city_npc(gs, _BAKER_UUID, "Bruno", "baker", _MARKET_ID)
    _set_scene_at(gs, _TAVERN_ID, _SCHOLAR_UUID)
    memory = _add_session_memory(gs, _SCHOLAR_UUID)

    NPCTicker(gs).tick(TurnOutputs())

    assert _hearsay_at(gs, _MARKET_ID) == []
    assert "propagated_on_departure" not in memory.tags


@allure.story("Memory preservation")
@allure.title("Evicting a bartender with no WITNESSED memories creates no hearsay")
def test_no_memories_means_no_hearsay() -> None:
    gs = _make_city_state(game_time="morning")
    _add_city_npc(gs, _BARTENDER_UUID, "Marco", "bartender", _TAVERN_ID)
    _add_city_npc(gs, _BAKER_UUID, "Bruno", "baker", _MARKET_ID)
    _set_scene_at(gs, _TAVERN_ID, _BARTENDER_UUID)

    NPCTicker(gs).tick(TurnOutputs())

    assert _hearsay_at(gs, _MARKET_ID) == []


@allure.story("Memory preservation")
@allure.title("Re-entry regression: evict, return, evict again — only one hearsay per recipient")
def test_second_eviction_after_return_does_not_duplicate_hearsay() -> None:
    gs = _make_city_state(game_time="morning")
    _add_city_npc(gs, _BARTENDER_UUID, "Marco", "bartender", _TAVERN_ID)
    _add_city_npc(gs, _BAKER_UUID, "Bruno", "baker", _MARKET_ID)
    scene = _set_scene_at(gs, _TAVERN_ID, _BARTENDER_UUID)
    _add_session_memory(gs, _BARTENDER_UUID)

    ticker = NPCTicker(gs)
    ticker.tick(TurnOutputs())
    # Simulate the bartender coming back and being evicted again in a later turn.
    scene.npcs_present = [SceneNPC(role="bartender", uuid=_BARTENDER_UUID)]
    gs.game_time = "morning"  # still a bartender-absent time of day
    ticker.tick(TurnOutputs())

    assert len(_hearsay_at(gs, _MARKET_ID)) == 1


@allure.story("Memory preservation")
@allure.title("Multiple simultaneous departures propagate memories independently")
def test_multiple_simultaneous_departures() -> None:
    gs = _make_city_state(game_time="night")
    _add_city_npc(gs, _GUARD_UUID, "Lucia", "guard", _TAVERN_ID)
    _add_city_npc(gs, _BAKER_UUID, "Bruno", "baker", _TAVERN_ID)
    # Scholar is always-present so it never gets evicted and only serves as a recipient.
    _add_city_npc(gs, _SCHOLAR_UUID, "Seneca", "scholar", _MARKET_ID)
    _set_scene_at(gs, _TAVERN_ID, _GUARD_UUID, _BAKER_UUID)
    _add_session_memory(gs, _GUARD_UUID, text="Lucia saw the player kick the chest.")
    _add_session_memory(gs, _BAKER_UUID, text="Bruno heard the player insult the prefect.")

    NPCTicker(gs).tick(TurnOutputs())

    hearsay_at_market = _hearsay_at(gs, _MARKET_ID)
    assert len(hearsay_at_market) == 2
    texts = {node.text for node in hearsay_at_market}
    assert "Lucia saw the player kick the chest." in texts
    assert "Bruno heard the player insult the prefect." in texts
