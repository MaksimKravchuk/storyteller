"""Regression tests for :mod:`knowledge.memory_preservation`.

Covers the pure function ``preserve_departing_npc_memories`` in
isolation from :class:`cast.npc_ticker.NPCTicker` — the integration
path through the ticker is tested in ``tests/test_npc_ticker.py``.
"""

from __future__ import annotations

import allure

from knowledge.graph import KnowledgeGraph
from knowledge.memory_preservation import (
    _DEPARTURE_PROPAGATION_TAG,
    _MAX_MEMORIES_PER_DEPARTURE,
    preserve_departing_npc_memories,
)
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
from models.setting import Setting

pytestmark = [
    allure.epic("Knowledge Graph"),
    allure.feature("Departure memory preservation"),
]

_CITY_ID = "loc-city-rome"
_TAVERN_ID = "loc-tavern"
_MARKET_ID = "loc-market"
_FORUM_ID = "loc-forum"

_BARTENDER_ID = "npc-bartender"
_BAKER_ID = "npc-baker"
_MERCHANT_ID = "npc-merchant"

_MEMORY_TEXT = "The player confessed to stealing the senator's ring."


def _setting() -> Setting:
    return Setting(name="Rome", time_period="1 AD", region="Italy", summary="")


def _build_city_state() -> GameState:
    """Build a Rome city with a tavern + a market + a forum.

    Layout::

        Rome (city)
          ├── Tavern  — houses the bartender (the departing NPC)
          ├── Market  — houses the baker (the eventual hearsay recipient)
          └── Forum   — houses the merchant (another hearsay recipient)
    """
    game_state = GameState(setting=_setting(), knowledge_graph=KnowledgeGraph())
    game_state.locations[_CITY_ID] = Location(
        name="Rome",
        location_type="city",
        parent_location_id=None,
    )
    game_state.locations[_TAVERN_ID] = Location(
        name="Tavern",
        location_type="building",
        parent_location_id=_CITY_ID,
        npcs_present=[_BARTENDER_ID],
    )
    game_state.locations[_MARKET_ID] = Location(
        name="Market",
        location_type="building",
        parent_location_id=_CITY_ID,
        npcs_present=[_BAKER_ID],
    )
    game_state.locations[_FORUM_ID] = Location(
        name="Forum",
        location_type="plaza",
        parent_location_id=_CITY_ID,
        npcs_present=[_MERCHANT_ID],
    )

    game_state.npcs[_BARTENDER_ID] = NPCCard(
        uuid=_BARTENDER_ID,
        name="Marco",
        biography="Keeps the tavern running.",
        occupation="bartender",
        knowledge_scope="city",
        attributes={"education": 2, "social_status": 3},
        location_id=_TAVERN_ID,
    )
    game_state.npcs[_BAKER_ID] = NPCCard(
        uuid=_BAKER_ID,
        name="Bruno",
        biography="Bakes bread every dawn.",
        occupation="baker",
        knowledge_scope="city",
        attributes={"education": 2, "social_status": 3},
        location_id=_MARKET_ID,
    )
    game_state.npcs[_MERCHANT_ID] = NPCCard(
        uuid=_MERCHANT_ID,
        name="Livia",
        biography="Sells spices from the east.",
        occupation="merchant",
        knowledge_scope="city",
        attributes={"education": 3, "social_status": 4},
        location_id=_FORUM_ID,
    )

    game_state.knowledge_graph.register_actor_node(_BARTENDER_ID, label="Marco")
    game_state.knowledge_graph.register_actor_node(_BAKER_ID, label="Bruno")
    game_state.knowledge_graph.register_actor_node(_MERCHANT_ID, label="Livia")
    return game_state


def _add_session_memory(
    graph: KnowledgeGraph,
    npc_id: str,
    *,
    text: str = _MEMORY_TEXT,
    timestamp: float | None = 1.0,
    tags: list[str] | None = None,
) -> KnowledgeNode:
    """Attach a PERSONAL_EXPERIENCE + SESSION memory to ``npc_id`` via WITNESSED."""
    memory = KnowledgeNode(
        text=text,
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.PERSONAL_EXPERIENCE,
        canon=CanonSource.SESSION,
        location_id=_TAVERN_ID,
        timestamp=timestamp,
        tags=list(tags) if tags else [],
    )
    graph.add_node(memory)
    graph.add_edge(npc_id, memory.uuid, EdgeType.WITNESSED)
    return memory


def _hearsay_nodes_at(graph: KnowledgeGraph, location_id: str) -> list[KnowledgeNode]:
    return [
        node for node in graph.all_nodes() if node.source == KnowledgeSource.HEARSAY and node.location_id == location_id
    ]


@allure.story("preserve_departing_npc_memories")
@allure.title("NPC with no WITNESSED memories: preservation is a no-op")
def test_no_memories_returns_empty() -> None:
    game_state = _build_city_state()
    graph = game_state.knowledge_graph

    created_ids = preserve_departing_npc_memories(graph, game_state, _BARTENDER_ID, _TAVERN_ID)

    assert created_ids == []
    assert _hearsay_nodes_at(graph, _MARKET_ID) == []
    assert _hearsay_nodes_at(graph, _FORUM_ID) == []


@allure.story("preserve_departing_npc_memories")
@allure.title("Single session memory propagates as HEARSAY to same-city non-witnesses with TOLD_BY")
def test_single_session_memory_propagates_to_same_city_non_witnesses() -> None:
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    memory = _add_session_memory(graph, _BARTENDER_ID)

    created_ids = preserve_departing_npc_memories(graph, game_state, _BARTENDER_ID, _TAVERN_ID)

    # One hearsay node per same-city non-witness (baker + merchant).
    assert len(created_ids) == 2
    for hearsay_id in created_ids:
        hearsay = graph.get_node(hearsay_id)
        assert hearsay is not None
        assert hearsay.text == _MEMORY_TEXT
        assert hearsay.scope == KnowledgeScope.LOCAL
        assert hearsay.source == KnowledgeSource.HEARSAY
        assert hearsay.canon == CanonSource.SESSION
        assert hearsay.location_id in {_MARKET_ID, _FORUM_ID}

        told_by_edges = [
            (target, edge_attrs)
            for _, target, edge_attrs in graph.digraph.out_edges(hearsay_id, data=True)
            if edge_attrs.get("edge_type") == EdgeType.TOLD_BY
        ]
        assert len(told_by_edges) == 1
        target_id, edge_attrs = told_by_edges[0]
        assert target_id == _BARTENDER_ID
        assert edge_attrs.get("recipient_id") in {_BAKER_ID, _MERCHANT_ID}

    # Original memory is tagged so a second eviction is a cheap no-op.
    assert _DEPARTURE_PROPAGATION_TAG in memory.tags
    # Original WITNESSED edge is untouched — the bartender keeps their own memory.
    bartender_targets = {target for target, _ in graph.get_edges_from(_BARTENDER_ID)}
    assert memory.uuid in bartender_targets


@allure.story("preserve_departing_npc_memories")
@allure.title("Historical-canon memories are never propagated on departure")
def test_historical_canon_memories_not_propagated() -> None:
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    historical = KnowledgeNode(
        text="Rome was founded in 753 BC.",
        scope=KnowledgeScope.CITY,
        source=KnowledgeSource.FACT,
        canon=CanonSource.HISTORICAL,
    )
    graph.add_node(historical)
    graph.add_edge(_BARTENDER_ID, historical.uuid, EdgeType.WITNESSED)

    created_ids = preserve_departing_npc_memories(graph, game_state, _BARTENDER_ID, _TAVERN_ID)

    assert created_ids == []
    assert _DEPARTURE_PROPAGATION_TAG not in historical.tags


@allure.story("preserve_departing_npc_memories")
@allure.title("Hearsay-source memories linked via WITNESSED are skipped (only personal experience propagates)")
def test_hearsay_source_memories_skipped() -> None:
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    gossip = KnowledgeNode(
        text="Another NPC already told the bartender a rumour.",
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.HEARSAY,
        canon=CanonSource.SESSION,
        location_id=_TAVERN_ID,
    )
    graph.add_node(gossip)
    graph.add_edge(_BARTENDER_ID, gossip.uuid, EdgeType.WITNESSED)

    created_ids = preserve_departing_npc_memories(graph, game_state, _BARTENDER_ID, _TAVERN_ID)

    assert created_ids == []


@allure.story("preserve_departing_npc_memories")
@allure.title("Memories already tagged propagated_on_departure are skipped")
def test_pre_tagged_memory_is_skipped() -> None:
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    _add_session_memory(graph, _BARTENDER_ID, tags=[_DEPARTURE_PROPAGATION_TAG])

    created_ids = preserve_departing_npc_memories(graph, game_state, _BARTENDER_ID, _TAVERN_ID)

    assert created_ids == []


@allure.story("preserve_departing_npc_memories")
@allure.title("Calling preserve twice is idempotent — the tag blocks the second pass")
def test_second_call_is_idempotent() -> None:
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    _add_session_memory(graph, _BARTENDER_ID)

    first = preserve_departing_npc_memories(graph, game_state, _BARTENDER_ID, _TAVERN_ID)
    second = preserve_departing_npc_memories(graph, game_state, _BARTENDER_ID, _TAVERN_ID)

    assert len(first) == 2
    assert second == []
    # No duplicate hearsay nodes were created on the second pass.
    assert len(_hearsay_nodes_at(graph, _MARKET_ID)) == 1
    assert len(_hearsay_nodes_at(graph, _FORUM_ID)) == 1


@allure.story("preserve_departing_npc_memories")
@allure.title("Memories with empty or whitespace-only text are skipped")
def test_empty_text_memory_is_skipped() -> None:
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    _add_session_memory(graph, _BARTENDER_ID, text="   ")

    created_ids = preserve_departing_npc_memories(graph, game_state, _BARTENDER_ID, _TAVERN_ID)

    assert created_ids == []


@allure.story("preserve_departing_npc_memories")
@allure.title("Isolated scene with no recipients still tags memories to avoid re-scanning")
def test_no_recipients_still_tags_memories() -> None:
    game_state = GameState(setting=_setting(), knowledge_graph=KnowledgeGraph())
    game_state.locations[_CITY_ID] = Location(
        name="Rome",
        location_type="city",
        parent_location_id=None,
    )
    game_state.locations[_TAVERN_ID] = Location(
        name="Tavern",
        location_type="building",
        parent_location_id=_CITY_ID,
        npcs_present=[_BARTENDER_ID],
    )
    game_state.npcs[_BARTENDER_ID] = NPCCard(
        uuid=_BARTENDER_ID,
        name="Marco",
        occupation="bartender",
        location_id=_TAVERN_ID,
    )
    graph = game_state.knowledge_graph
    graph.register_actor_node(_BARTENDER_ID, label="Marco")
    memory = _add_session_memory(graph, _BARTENDER_ID)

    created_ids = preserve_departing_npc_memories(graph, game_state, _BARTENDER_ID, _TAVERN_ID)

    assert created_ids == []
    assert _DEPARTURE_PROPAGATION_TAG in memory.tags


@allure.story("preserve_departing_npc_memories")
@allure.title("Unknown scene_location_id is handled gracefully (no recipients, no crash)")
def test_scene_location_not_in_locations_map() -> None:
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    memory = _add_session_memory(graph, _BARTENDER_ID)

    created_ids = preserve_departing_npc_memories(graph, game_state, _BARTENDER_ID, "loc-nonexistent")

    assert created_ids == []
    # The memory is still tagged so re-eviction is a cheap no-op.
    assert _DEPARTURE_PROPAGATION_TAG in memory.tags


@allure.story("preserve_departing_npc_memories")
@allure.title("Memory count is capped at _MAX_MEMORIES_PER_DEPARTURE (newest first)")
def test_memory_count_capped_newest_first() -> None:
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    over_cap = _MAX_MEMORIES_PER_DEPARTURE + 5
    for idx in range(over_cap):
        _add_session_memory(
            graph,
            _BARTENDER_ID,
            text="memory #{0}".format(idx),
            timestamp=float(idx),
        )

    created_ids = preserve_departing_npc_memories(graph, game_state, _BARTENDER_ID, _TAVERN_ID)

    # Two recipients per propagated memory; cap applies to memories, not recipients.
    assert len(created_ids) == _MAX_MEMORIES_PER_DEPARTURE * 2
    # Spot-check the oldest memory was NOT propagated (no hearsay text matches).
    propagated_texts = {graph.get_node(uid).text for uid in created_ids}  # type: ignore[union-attr]
    assert "memory #0" not in propagated_texts
    # ...and the newest one WAS.
    assert "memory #{0}".format(over_cap - 1) in propagated_texts


@allure.story("preserve_departing_npc_memories")
@allure.title("Non-WITNESSED outgoing edges on the NPC are ignored")
def test_non_witnessed_edges_ignored() -> None:
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    other = KnowledgeNode(
        text="The bartender knows about the recent festival.",
        scope=KnowledgeScope.CITY,
        source=KnowledgeSource.FACT,
        canon=CanonSource.HISTORICAL,
    )
    graph.add_node(other)
    graph.add_edge(_BARTENDER_ID, other.uuid, EdgeType.KNOWS_ABOUT)
    session_memory = _add_session_memory(graph, _BARTENDER_ID)

    created_ids = preserve_departing_npc_memories(graph, game_state, _BARTENDER_ID, _TAVERN_ID)

    # Only the WITNESSED session memory triggers propagation.
    assert len(created_ids) == 2
    for hearsay_id in created_ids:
        hearsay = graph.get_node(hearsay_id)
        assert hearsay is not None
        assert hearsay.text == session_memory.text


@allure.story("preserve_departing_npc_memories")
@allure.title("Propagated hearsay surfaces via KnowledgeQueryEngine.get_context_for_npc on the recipient")
def test_propagated_hearsay_surfaces_in_recipient_context() -> None:
    """KER-9 acceptance criterion: evicted NPC's memory must be findable via the rumor channel."""
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    _add_session_memory(graph, _BARTENDER_ID)

    preserve_departing_npc_memories(graph, game_state, _BARTENDER_ID, _TAVERN_ID)

    engine = KnowledgeQueryEngine(graph)
    baker_context = engine.get_context_for_npc(game_state.npcs[_BAKER_ID])
    merchant_context = engine.get_context_for_npc(game_state.npcs[_MERCHANT_ID])

    assert "[Heard from someone] " in baker_context
    assert _MEMORY_TEXT in baker_context
    assert "[Heard from someone] " in merchant_context
    assert _MEMORY_TEXT in merchant_context
