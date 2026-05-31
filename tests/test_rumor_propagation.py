"""Regression tests for knowledge.rumor.propagate_rumors."""

from __future__ import annotations

from uuid import UUID

import allure

from knowledge import graph as _graph, node as _node, query as _query, rumor as _rumor
from knowledge.rumor_scope import non_witness_city_npcs
from models.game_state import GameState
from models.location import Location
from models.npc_card import NPCCard
from models.setting import Setting
from tests._uuid_helpers import make_uuid
from timeline.event import GameEvent

KnowledgeGraph = _graph.KnowledgeGraph
CanonSource = _node.CanonSource
EdgeType = _node.EdgeType
KnowledgeScope = _node.KnowledgeScope
KnowledgeSource = _node.KnowledgeSource
KnowledgeQueryEngine = _query.KnowledgeQueryEngine
propagate_rumors = _rumor.propagate_rumors

pytestmark = [
    allure.epic("Knowledge Graph"),
    allure.feature("Rumor propagation"),
]

_CITY_ID = make_uuid("loc-city-rome")
_FORUM_ID = make_uuid("loc-forum")
_TAVERN_ID = make_uuid("loc-tavern")
_MARKET_ID = make_uuid("loc-market")

_WITNESS_ID = make_uuid("npc-witness")
_ABSENT_ID = make_uuid("npc-absent")
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


def _hearsay_nodes_at(graph: KnowledgeGraph, location_id: UUID) -> list:
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
@allure.title("Propagated HEARSAY does not leak to a later co-located non-recipient")
def test_propagated_hearsay_does_not_leak_to_later_colocated_nonrecipient() -> None:
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    propagate_rumors(graph, game_state, [_make_event(scope="city")])
    late_arrival_id = make_uuid("npc-late-arrival")
    game_state.npcs[late_arrival_id] = NPCCard(
        uuid=late_arrival_id,
        name="Julia",
        biography="A patron who arrived after the rumor was told.",
        occupation="patron",
        knowledge_scope="city",
        attributes={"education": 3, "social_status": 3},
        location_id=_TAVERN_ID,
    )

    engine = KnowledgeQueryEngine(graph)
    recipient_context = engine.get_context_for_npc(game_state.npcs[_ABSENT_ID])
    nonrecipient_context = engine.get_context_for_npc(game_state.npcs[late_arrival_id])

    assert _EVENT_TEXT in recipient_context
    assert _EVENT_TEXT not in nonrecipient_context


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
@allure.title("Propagated rumor hearsay carries the current game_clock as its timestamp")
def test_rumor_hearsay_timestamp_is_game_clock() -> None:
    game_state = _build_city_state()
    rumor_clock = float(73)
    game_state.game_clock = rumor_clock
    graph = game_state.knowledge_graph

    created_ids = propagate_rumors(graph, game_state, [_make_event(scope="city")])

    assert len(created_ids) == 1
    hearsay = graph.get_node(created_ids[0])
    assert hearsay is not None
    # The event's game_clock must reach the hearsay timestamp; a dropped /
    # None game_time would surface here.
    assert hearsay.timestamp == rumor_clock


@allure.story("propagate_rumors")
@allure.title("An NPC standing at the event location is excluded even when absent from the witness list")
def test_npc_at_event_location_excluded_from_recipients() -> None:
    game_state = _build_city_state()
    lurker_id = make_uuid("npc-lurker")
    # The lurker's location_id is the Forum (the event site) but they are not
    # listed in the Forum's npcs_present, so they never enter the witness list.
    # They must still be excluded as a recipient because they share the event
    # location — proving the event_location_id reaches the listener filter.
    game_state.npcs[lurker_id] = NPCCard(
        uuid=lurker_id,
        name="Lurker",
        occupation="loiterer",
        knowledge_scope="city",
        attributes={"education": 2, "social_status": 2},
        location_id=_FORUM_ID,
    )
    graph = game_state.knowledge_graph

    created_ids = propagate_rumors(graph, game_state, [_make_event(scope="city")])

    # Only the absent tavern NPC receives the rumor — the Forum lurker does not.
    assert len(created_ids) == 1
    assert _hearsay_nodes_at(graph, _FORUM_ID) == []
    hearsay = graph.get_node(created_ids[0])
    assert hearsay is not None
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


_REGION_ID = make_uuid("loc-region")
_SUBROOM_ID = make_uuid("loc-subroom")
_OUTSIDER_ID = make_uuid("npc-outsider")
_DEEP_ID = make_uuid("npc-deep")


def _npc_at(location_id: UUID) -> NPCCard:
    return NPCCard(name="Resident", occupation="local", knowledge_scope="city", location_id=location_id)


@allure.story("non_witness_city_npcs")
@allure.title("A city that itself has a parent region still anchors the walk so same-city siblings are reached")
def test_city_root_anchors_at_city_with_parent() -> None:
    game_state = GameState(setting=_setting(), knowledge_graph=KnowledgeGraph())
    game_state.locations[_REGION_ID] = Location(name="Latium", location_type="region", parent_location_id=None)
    game_state.locations[_CITY_ID] = Location(name="Rome", location_type="city", parent_location_id=_REGION_ID)
    game_state.locations[_FORUM_ID] = Location(
        name="Forum",
        location_type="plaza",
        parent_location_id=_CITY_ID,
    )
    game_state.locations[_TAVERN_ID] = Location(
        name="Tavern",
        location_type="building",
        parent_location_id=_CITY_ID,
    )
    # A sibling-building resident in the same city Rome.
    game_state.npcs[_OUTSIDER_ID] = _npc_at(_TAVERN_ID)

    recipients = non_witness_city_npcs(game_state, _FORUM_ID, [])
    recipient_ids = {npc_id for npc_id, _loc in recipients}

    # The walk must recognise Rome as the city anchor (a city node counts even
    # though it has a parent region), so the tavern sibling is reachable. If
    # the anchor fell back to the Forum itself, the tavern resident would be
    # wrongly excluded.
    assert _OUTSIDER_ID in recipient_ids


@allure.story("non_witness_city_npcs")
@allure.title("The city-anchor walk terminates on a parent cycle instead of looping forever")
def test_city_root_terminates_on_cycle() -> None:
    loc_a = make_uuid("loc-cycle-a")
    loc_b = make_uuid("loc-cycle-b")
    game_state = GameState(setting=_setting(), knowledge_graph=KnowledgeGraph())
    # Two non-city locations whose parents point at each other form a cycle.
    game_state.locations[loc_a] = Location(name="A", location_type="building", parent_location_id=loc_b)
    game_state.locations[loc_b] = Location(name="B", location_type="building", parent_location_id=loc_a)

    # The visited-set guard must break the cycle and return a result; without
    # it this call would loop forever.
    recipients = non_witness_city_npcs(game_state, loc_a, [])

    assert recipients == []


@allure.story("non_witness_city_npcs")
@allure.title("Reachability spans multiple nesting levels regardless of location insertion order")
def test_reachable_descendants_spans_deep_nesting() -> None:
    game_state = GameState(setting=_setting(), knowledge_graph=KnowledgeGraph())
    game_state.locations[_CITY_ID] = Location(name="Rome", location_type="city", parent_location_id=None)
    game_state.locations[_FORUM_ID] = Location(
        name="Forum",
        location_type="plaza",
        parent_location_id=_CITY_ID,
    )
    # Insert the grandchild subroom BEFORE its parent building so the
    # fixed-point walk must run a second pass to reach it. If the loop exits
    # after a single pass, the deep NPC is wrongly dropped.
    game_state.locations[_SUBROOM_ID] = Location(
        name="Back room",
        location_type="building",
        parent_location_id=_TAVERN_ID,
    )
    game_state.locations[_TAVERN_ID] = Location(
        name="Tavern",
        location_type="building",
        parent_location_id=_CITY_ID,
    )
    game_state.npcs[_DEEP_ID] = _npc_at(_SUBROOM_ID)

    recipients = non_witness_city_npcs(game_state, _FORUM_ID, [])
    recipient_ids = {npc_id for npc_id, _loc in recipients}

    # The deeply-nested NPC shares the city and must be reached.
    assert _DEEP_ID in recipient_ids
