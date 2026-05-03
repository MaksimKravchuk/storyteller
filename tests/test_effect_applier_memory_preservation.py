"""Regression tests: REMOVE_NPC must preserve session memories as hearsay.

These tests cover the hard-removal path
(:meth:`timeline.effect_applier.EffectApplier._remove_npc` —
deaths, forced moves) and assert that the departing NPC's
session-canon ``PERSONAL_EXPERIENCE`` memories survive eviction as
``HEARSAY`` for same-city non-witnesses, mirroring the soft-removal
:class:`cast.npc_ticker.NPCTicker` path. The pure-function unit
tests for the underlying primitive live in
``tests/test_memory_preservation.py``; this file exercises the
EffectApplier wiring at the consumer-side seam.
"""

from __future__ import annotations

from uuid import UUID

import allure

from knowledge.graph import KnowledgeGraph
from knowledge.node import (
    CanonSource,
    EdgeType,
    KnowledgeNode,
    KnowledgeScope,
    KnowledgeSource,
)
from knowledge.query import KnowledgeQueryEngine
from models import game_state as _gs, location as _loc, npc_card as _npc, setting as _setting
from tests._uuid_helpers import make_uuid
from timeline.effect_applier import EffectApplier
from timeline.event import EventEffect

GameState = _gs.GameState
Location = _loc.Location
NPCCard = _npc.NPCCard
Setting = _setting.Setting

pytestmark = [
    allure.epic("Game Timeline"),
    allure.feature("Effect application"),
]

_CITY_ID = make_uuid("loc-city-rome")
_TAVERN_ID = make_uuid("loc-tavern")
_MARKET_ID = make_uuid("loc-market")
_FORUM_ID = make_uuid("loc-forum")

_VICTIM_ID = make_uuid("npc-victim")
_BAKER_ID = make_uuid("npc-baker")
_MERCHANT_ID = make_uuid("npc-merchant")

_MEMORY_TEXT = "The player confessed to stealing the senator's ring."


def _build_city_state() -> GameState:
    """Build a Rome city with three locations: tavern (victim), market (baker), forum (merchant)."""
    gs = GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=KnowledgeGraph(),
    )
    gs.locations[_CITY_ID] = Location(
        name="Rome",
        location_type="city",
        parent_location_id=None,
    )
    gs.locations[_TAVERN_ID] = Location(
        name="Tavern",
        location_type="building",
        parent_location_id=_CITY_ID,
        npcs_present=[_VICTIM_ID],
    )
    gs.locations[_MARKET_ID] = Location(
        name="Market",
        location_type="building",
        parent_location_id=_CITY_ID,
        npcs_present=[_BAKER_ID],
    )
    gs.locations[_FORUM_ID] = Location(
        name="Forum",
        location_type="plaza",
        parent_location_id=_CITY_ID,
        npcs_present=[_MERCHANT_ID],
    )
    victim = NPCCard(name="Marco", occupation="bartender", location_id=_TAVERN_ID)
    victim.uuid = _VICTIM_ID
    baker = NPCCard(name="Bruno", occupation="baker", location_id=_MARKET_ID)
    baker.uuid = _BAKER_ID
    merchant = NPCCard(name="Livia", occupation="merchant", location_id=_FORUM_ID)
    merchant.uuid = _MERCHANT_ID
    gs.npcs[_VICTIM_ID] = victim
    gs.npcs[_BAKER_ID] = baker
    gs.npcs[_MERCHANT_ID] = merchant
    gs.knowledge_graph.register_actor_node(_VICTIM_ID, label="Marco")
    gs.knowledge_graph.register_actor_node(_BAKER_ID, label="Bruno")
    gs.knowledge_graph.register_actor_node(_MERCHANT_ID, label="Livia")
    return gs


def _add_session_memory(
    graph: KnowledgeGraph,
    npc_id: UUID,
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
    graph.add_node(memory)
    graph.add_edge(npc_id, memory.uuid, EdgeType.WITNESSED)
    return memory


def _hearsay_at(graph: KnowledgeGraph, location_id: UUID) -> list[KnowledgeNode]:
    return [
        node for node in graph.all_nodes() if node.source == KnowledgeSource.HEARSAY and node.location_id == location_id
    ]


@allure.story("Remove NPC")
@allure.title("REMOVE_NPC propagates the victim's session memory as HEARSAY for same-city non-witnesses")
def test_remove_npc_propagates_session_memory_as_hearsay() -> None:
    gs = _build_city_state()
    graph = gs.knowledge_graph
    _add_session_memory(graph, _VICTIM_ID)

    EffectApplier(gs, graph).apply(
        EventEffect(effect_type="REMOVE_NPC", target_id=str(_VICTIM_ID), effect_data={}),
    )

    market_hearsay = _hearsay_at(graph, _MARKET_ID)
    forum_hearsay = _hearsay_at(graph, _FORUM_ID)
    assert len(market_hearsay) == 1
    assert len(forum_hearsay) == 1
    assert market_hearsay[0].text == _MEMORY_TEXT
    assert forum_hearsay[0].text == _MEMORY_TEXT


@allure.story("Remove NPC")
@allure.title("REMOVE_NPC tags the original memory so a re-removal does not duplicate hearsay")
def test_remove_npc_is_idempotent_when_called_twice() -> None:
    gs = _build_city_state()
    graph = gs.knowledge_graph
    _add_session_memory(graph, _VICTIM_ID)

    applier = EffectApplier(gs, graph)
    applier.apply(EventEffect(effect_type="REMOVE_NPC", target_id=str(_VICTIM_ID), effect_data={}))
    applier.apply(EventEffect(effect_type="REMOVE_NPC", target_id=str(_VICTIM_ID), effect_data={}))

    assert len(_hearsay_at(graph, _MARKET_ID)) == 1
    assert len(_hearsay_at(graph, _FORUM_ID)) == 1


@allure.story("Remove NPC")
@allure.title("REMOVE_NPC writes a TOLD_BY edge from each hearsay node back to the removed NPC")
def test_remove_npc_hearsay_carries_told_by_provenance() -> None:
    gs = _build_city_state()
    graph = gs.knowledge_graph
    _add_session_memory(graph, _VICTIM_ID)

    EffectApplier(gs, graph).apply(
        EventEffect(effect_type="REMOVE_NPC", target_id=str(_VICTIM_ID), effect_data={}),
    )

    market_hearsay = _hearsay_at(graph, _MARKET_ID)
    assert len(market_hearsay) == 1
    told_by_edges = [
        (target, edge_attrs)
        for _, target, edge_attrs in graph.digraph.out_edges(market_hearsay[0].uuid, data=True)
        if edge_attrs.get("edge_type") == EdgeType.TOLD_BY
    ]
    assert len(told_by_edges) == 1
    target_id, edge_attrs = told_by_edges[0]
    assert target_id == _VICTIM_ID
    assert edge_attrs.get("recipient_id") == _BAKER_ID


@allure.story("Remove NPC")
@allure.title("REMOVE_NPC propagated hearsay surfaces in the recipient's KnowledgeQueryEngine context")
def test_remove_npc_hearsay_surfaces_via_query_engine() -> None:
    """Consumer-side seam: the baker, at a different city location, must see the rumor."""
    gs = _build_city_state()
    graph = gs.knowledge_graph
    _add_session_memory(graph, _VICTIM_ID)

    EffectApplier(gs, graph).apply(
        EventEffect(effect_type="REMOVE_NPC", target_id=str(_VICTIM_ID), effect_data={}),
    )

    baker_context = KnowledgeQueryEngine(graph).get_context_for_npc(gs.npcs[_BAKER_ID])
    assert "[Heard from someone] " in baker_context
    assert _MEMORY_TEXT in baker_context


@allure.story("Remove NPC")
@allure.title("REMOVE_NPC on an NPC with no session memories still mutates state and creates no hearsay")
def test_remove_npc_with_no_memories_creates_no_hearsay() -> None:
    gs = _build_city_state()
    graph = gs.knowledge_graph

    EffectApplier(gs, graph).apply(
        EventEffect(effect_type="REMOVE_NPC", target_id=str(_VICTIM_ID), effect_data={}),
    )

    assert _hearsay_at(graph, _MARKET_ID) == []
    assert _hearsay_at(graph, _FORUM_ID) == []
    assert _VICTIM_ID not in gs.npcs


@allure.story("Remove NPC")
@allure.title("REMOVE_NPC for an NPC with no location_id is safe and creates no hearsay")
def test_remove_npc_without_location_does_not_raise() -> None:
    gs = _build_city_state()
    graph = gs.knowledge_graph
    drifter_id = make_uuid("npc-drifter")
    drifter = NPCCard(name="Drifter", occupation="vagrant", location_id=None)
    drifter.uuid = drifter_id
    gs.npcs[drifter_id] = drifter
    graph.register_actor_node(drifter_id, label="Drifter")

    # Without a location to anchor same-city scope, preservation is
    # skipped entirely — passing None to the rumor-scope walker would
    # incorrectly fan hearsay out to every top-level location.
    EffectApplier(gs, graph).apply(
        EventEffect(effect_type="REMOVE_NPC", target_id=str(drifter_id), effect_data={}),
    )

    assert drifter_id not in gs.npcs
    assert _hearsay_at(graph, _MARKET_ID) == []
    assert _hearsay_at(graph, _FORUM_ID) == []


@allure.story("Remove NPC")
@allure.title("REMOVE_NPC keeps the original WITNESSED memory node in the graph (re-entry safety)")
def test_remove_npc_does_not_delete_the_underlying_memory_node() -> None:
    gs = _build_city_state()
    graph = gs.knowledge_graph
    memory = _add_session_memory(graph, _VICTIM_ID)

    EffectApplier(gs, graph).apply(
        EventEffect(effect_type="REMOVE_NPC", target_id=str(_VICTIM_ID), effect_data={}),
    )

    # The underlying personal-experience node is preserved; only the
    # NPC card is gone. The query engine surfaces the propagated rumor
    # for other NPCs (asserted in the surface test above).
    assert graph.get_node(memory.uuid) is not None
