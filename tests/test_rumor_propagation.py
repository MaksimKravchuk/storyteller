"""Regression tests for knowledge.rumor.propagate_rumors."""

from __future__ import annotations

import allure

from knowledge.graph import KnowledgeGraph
from knowledge.node import (
    CanonSource,
    EdgeType,
    KnowledgeScope,
    KnowledgeSource,
)
from knowledge.query import KnowledgeQueryEngine
from knowledge.rumor import propagate_rumors
from models.game_state import GameState
from models.location import Location
from models.npc_card import NPCCard
from models.setting import Setting
from timeline.event import GameEvent

pytestmark = [
    allure.epic("Knowledge Graph"),
    allure.feature("Rumor propagation"),
]

_CITY_ID = "loc-city-rome"
_FORUM_ID = "loc-forum"
_TAVERN_ID = "loc-tavern"
_MARKET_ID = "loc-market"

_WITNESS_ID = "npc-witness"
_ABSENT_ID = "npc-absent"
_EVENT_TEXT = "A ceremonial explosion rocked the Forum."


def _setting() -> Setting:
    return Setting(name="Rome", time_period="1 AD", region="Italy", summary="")


def _build_city_state() -> GameState:
    """Build a game state with a 3-location city hierarchy and 2 NPCs.

    Layout:
        Rome (city)
          ├── Forum (plaza) — houses the witness NPC
          ├── Tavern (building) — houses the absent NPC
          └── Market (building) — unused, proves the reverse walk
    """
    game_state = GameState(setting=_setting(), knowledge_graph=KnowledgeGraph())
    game_state.locations[_CITY_ID] = Location(
        name="Rome",
        location_type="city",
        parent_location_id=None,
    )
    game_state.locations[_FORUM_ID] = Location(
        name="Forum",
        location_type="plaza",
        parent_location_id=_CITY_ID,
        npcs_present=[_WITNESS_ID],
    )
    game_state.locations[_TAVERN_ID] = Location(
        name="Tavern",
        location_type="building",
        parent_location_id=_CITY_ID,
        npcs_present=[_ABSENT_ID],
    )
    game_state.locations[_MARKET_ID] = Location(
        name="Market",
        location_type="building",
        parent_location_id=_CITY_ID,
    )

    witness = NPCCard(
        uuid=_WITNESS_ID,
        name="Marcus",
        biography="A Roman soldier on duty at the Forum.",
        occupation="legionary",
        knowledge_scope="city",
        attributes={"education": 3, "social_status": 4},
        location_id=_FORUM_ID,
    )
    absent = NPCCard(
        uuid=_ABSENT_ID,
        name="Livia",
        biography="A tavern keeper who missed the explosion.",
        occupation="barkeep",
        knowledge_scope="city",
        attributes={"education": 2, "social_status": 3},
        location_id=_TAVERN_ID,
    )

    game_state.npcs[_WITNESS_ID] = witness
    game_state.npcs[_ABSENT_ID] = absent
    return game_state


def _make_event(*, scope: str) -> GameEvent:
    return GameEvent(
        name="Ceremonial explosion",
        scheduled_at=float(0),
        duration=float(1),
        location_id=_FORUM_ID,
        scope=scope,
        on_complete_description=_EVENT_TEXT,
    )


def _hearsay_nodes_at(graph: KnowledgeGraph, location_id: str) -> list:
    return [
        node for node in graph.all_nodes() if node.source == KnowledgeSource.HEARSAY and node.location_id == location_id
    ]


@allure.story("propagate_rumors")
@allure.title("CITY-scope event creates a HEARSAY node and TOLD_BY edge for absent same-city NPCs")
def test_city_scope_propagates_to_absent_npc_in_same_city() -> None:
    """Absent NPC B in Rome gets a LOCAL HEARSAY node at its own location with a TOLD_BY edge to witness A."""
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    event = _make_event(scope="city")

    created_ids = propagate_rumors(graph, game_state, [event])

    assert len(created_ids) == 1
    hearsay_id = created_ids[0]
    hearsay = graph.get_node(hearsay_id)
    assert hearsay is not None
    assert hearsay.text == _EVENT_TEXT
    assert hearsay.scope == KnowledgeScope.LOCAL
    assert hearsay.source == KnowledgeSource.HEARSAY
    assert hearsay.canon == CanonSource.SESSION
    assert hearsay.location_id == _TAVERN_ID

    # The TOLD_BY edge points from the hearsay node to the originating witness.
    told_by_targets = [
        (target, edge_attrs)
        for _, target, edge_attrs in graph.digraph.out_edges(hearsay_id, data=True)
        if edge_attrs.get("edge_type") == EdgeType.TOLD_BY
    ]
    assert len(told_by_targets) == 1
    target_id, edge_attrs = told_by_targets[0]
    assert target_id == _WITNESS_ID
    assert edge_attrs.get("recipient_id") == _ABSENT_ID


@allure.story("propagate_rumors")
@allure.title("Propagated HEARSAY surfaces for the absent NPC via KnowledgeQueryEngine.get_context_for_npc")
def test_hearsay_surfaces_in_absent_npc_context() -> None:
    """The absent NPC's Actor-side context block contains the '[Heard from someone] ' HEARSAY line."""
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    propagate_rumors(graph, game_state, [_make_event(scope="city")])

    engine = KnowledgeQueryEngine(graph)
    context = engine.get_context_for_npc(game_state.npcs[_ABSENT_ID])

    assert "[Heard from someone] " in context
    assert _EVENT_TEXT in context


@allure.story("propagate_rumors")
@allure.title("LOCAL-scope events do not propagate beyond the original witness")
def test_local_scope_does_not_propagate() -> None:
    """A LOCAL-scope event produces no HEARSAY nodes anywhere in the graph."""
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    event = _make_event(scope="local")

    created_ids = propagate_rumors(graph, game_state, [event])

    assert created_ids == []
    assert _hearsay_nodes_at(graph, _TAVERN_ID) == []
    assert _hearsay_nodes_at(graph, _MARKET_ID) == []


@allure.story("propagate_rumors")
@allure.title("CITY-scope events skip propagation when no witnesses are present at the event location")
def test_no_witnesses_skips_propagation() -> None:
    """Without a witness to serve as the TOLD_BY source, the rumor cannot originate."""
    game_state = _build_city_state()
    game_state.locations[_FORUM_ID].npcs_present = []
    graph = game_state.knowledge_graph

    created_ids = propagate_rumors(graph, game_state, [_make_event(scope="city")])

    assert created_ids == []


@allure.story("propagate_rumors")
@allure.title("Witnesses at the event location do not receive a HEARSAY copy of their own memory")
def test_witnesses_are_excluded_from_propagation() -> None:
    """The NPC already present at the Forum is the source, not a recipient."""
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    propagate_rumors(graph, game_state, [_make_event(scope="city")])

    witness_hearsay = _hearsay_nodes_at(graph, _FORUM_ID)
    assert witness_hearsay == []


@allure.story("propagate_rumors")
@allure.title("Region-scope events also propagate city-locally through the same path")
def test_region_scope_also_propagates() -> None:
    """REGION / COUNTRY / WORLD scope events share the same propagation pass."""
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    created_ids = propagate_rumors(graph, game_state, [_make_event(scope="region")])

    assert len(created_ids) == 1
    hearsay = graph.get_node(created_ids[0])
    assert hearsay is not None
    assert hearsay.source == KnowledgeSource.HEARSAY
    assert hearsay.location_id == _TAVERN_ID


@allure.story("propagate_rumors")
@allure.title("Events with no location_id are ignored")
def test_event_without_location_is_ignored() -> None:
    """Location-less events have no city anchor, so propagation is skipped."""
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    event = GameEvent(
        name="Omen",
        scheduled_at=float(0),
        duration=float(1),
        location_id=None,
        scope="city",
    )

    assert propagate_rumors(graph, game_state, [event]) == []
