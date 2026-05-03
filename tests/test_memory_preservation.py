"""Regression tests for :mod:`knowledge.memory_preservation`.

Covers the pure function ``preserve_departing_npc_memories`` in
isolation from :class:`cast.npc_ticker.NPCTicker` — the integration
path through the ticker is tested in ``tests/test_npc_ticker.py``.
"""

from __future__ import annotations

from uuid import UUID

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
from tests._uuid_helpers import make_uuid

pytestmark = [
    allure.epic("Knowledge Graph"),
    allure.feature("Departure memory preservation"),
]

_CITY_ID = make_uuid("loc-city-rome")
_TAVERN_ID = make_uuid("loc-tavern")
_MARKET_ID = make_uuid("loc-market")
_FORUM_ID = make_uuid("loc-forum")

_BARTENDER_ID = make_uuid("npc-bartender")
_BAKER_ID = make_uuid("npc-baker")
_MERCHANT_ID = make_uuid("npc-merchant")

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
    npc_id: UUID,
    *,
    text: str = _MEMORY_TEXT,
    timestamp: float | None = 1.0,
    pre_propagated: bool = False,
) -> KnowledgeNode:
    """Attach a PERSONAL_EXPERIENCE + SESSION memory to ``npc_id`` via WITNESSED.

    ``pre_propagated=True`` flips the ``_DEPARTURE_PROPAGATION_TAG``
    flag on the WITNESSED edge so the test simulates a memory whose
    departure-propagation has already happened for this witness.
    """
    memory = KnowledgeNode(
        text=text,
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.PERSONAL_EXPERIENCE,
        canon=CanonSource.SESSION,
        location_id=_TAVERN_ID,
        timestamp=timestamp,
    )
    graph.add_node(memory)
    graph.add_edge(npc_id, memory.uuid, EdgeType.WITNESSED)
    if pre_propagated:
        graph.flag_edge(npc_id, memory.uuid, _DEPARTURE_PROPAGATION_TAG)
    return memory


def _was_propagated(graph: KnowledgeGraph, npc_id: UUID, memory_id: UUID) -> bool:
    """Return True iff the ``npc_id → memory_id`` edge carries the propagation tag."""
    return graph.edge_has_flag(npc_id, memory_id, _DEPARTURE_PROPAGATION_TAG)


def _hearsay_nodes_at(graph: KnowledgeGraph, location_id: UUID) -> list[KnowledgeNode]:
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

    # The bartender's WITNESSED edge to the memory is tagged so a
    # second eviction of the same NPC is a cheap no-op. Co-witnesses
    # (none here) would still be free to propagate independently.
    assert _was_propagated(graph, _BARTENDER_ID, memory.uuid)
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
    # Historical-canon memories are skipped before the edge tag would be flipped.
    assert not _was_propagated(graph, _BARTENDER_ID, historical.uuid)


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
@allure.title("Witness edges already tagged propagated_on_departure are skipped")
def test_pre_tagged_witness_edge_is_skipped() -> None:
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    _add_session_memory(graph, _BARTENDER_ID, pre_propagated=True)

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
    assert _was_propagated(graph, _BARTENDER_ID, memory.uuid)


@allure.story("preserve_departing_npc_memories")
@allure.title("Unknown scene_location_id is handled gracefully (no recipients, no crash)")
def test_scene_location_not_in_locations_map() -> None:
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    memory = _add_session_memory(graph, _BARTENDER_ID)

    created_ids = preserve_departing_npc_memories(graph, game_state, _BARTENDER_ID, make_uuid("loc-nonexistent"))

    assert created_ids == []
    # The witness edge is still tagged so re-eviction is a cheap no-op.
    assert _was_propagated(graph, _BARTENDER_ID, memory.uuid)


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
    graph.add_edge(_BARTENDER_ID, other.uuid, EdgeType.TOLD_BY)
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


@allure.story("preserve_departing_npc_memories")
@allure.title("Co-witnesses sharing one canonical memory each propagate hearsay independently on departure")
def test_cowitnesses_propagate_independently_on_their_own_departure() -> None:
    """Per-edge idempotency: a shared canonical node must not let the
    first departing co-witness mute everyone else's propagation.

    Two co-witnesses share one LOCAL ``PERSONAL_EXPERIENCE`` node —
    the shape produced by the sub-linear co-witness broadcast in
    LOCAL-scope memory creation. After the first witness leaves the
    scene, the second witness's later departure must still fan a
    fresh hearsay copy out, attributed to *that* witness as
    ``told_by``. Locking this catches a regression where the
    propagation tag was stored on the node and the second departure
    became a silent no-op.
    """
    game_state = _build_city_state()
    graph = game_state.knowledge_graph
    # Move the merchant into the tavern so two NPCs can co-witness an event there.
    game_state.locations[_FORUM_ID].npcs_present.remove(_MERCHANT_ID)
    game_state.locations[_TAVERN_ID].npcs_present.append(_MERCHANT_ID)
    game_state.npcs[_MERCHANT_ID].location_id = _TAVERN_ID

    shared_memory = KnowledgeNode(
        text="The player insulted the praetor in the tavern.",
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.PERSONAL_EXPERIENCE,
        canon=CanonSource.SESSION,
        location_id=_TAVERN_ID,
        timestamp=1.0,
    )
    graph.add_node(shared_memory)
    graph.add_edge(_BARTENDER_ID, shared_memory.uuid, EdgeType.WITNESSED)
    graph.add_edge(_MERCHANT_ID, shared_memory.uuid, EdgeType.WITNESSED)

    # First witness leaves: hearsay propagates to baker (only same-city
    # non-witness still outside the tavern).
    first = preserve_departing_npc_memories(graph, game_state, _BARTENDER_ID, _TAVERN_ID)
    assert len(first) == 1
    assert _was_propagated(graph, _BARTENDER_ID, shared_memory.uuid)
    # The merchant's edge is still untagged — they are a separate witness.
    assert not _was_propagated(graph, _MERCHANT_ID, shared_memory.uuid)

    # Move the merchant out of the tavern so they are now also "departing".
    game_state.locations[_TAVERN_ID].npcs_present.remove(_MERCHANT_ID)
    game_state.npcs[_MERCHANT_ID].location_id = _FORUM_ID
    game_state.locations[_FORUM_ID].npcs_present.append(_MERCHANT_ID)

    # Second witness leaves: their independent edge means hearsay
    # propagates again, this time told_by the merchant.
    second = preserve_departing_npc_memories(graph, game_state, _MERCHANT_ID, _TAVERN_ID)
    assert len(second) == 1
    assert _was_propagated(graph, _MERCHANT_ID, shared_memory.uuid)

    told_by_uuids = {
        target
        for hearsay_id in (*first, *second)
        for _, target, edge_attrs in graph.digraph.out_edges(hearsay_id, data=True)
        if edge_attrs.get("edge_type") == EdgeType.TOLD_BY
    }
    assert told_by_uuids == {_BARTENDER_ID, _MERCHANT_ID}
