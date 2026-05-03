"""Knowledge graph — networkx-backed storage for all world knowledge and NPC memories."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import networkx as nx

from knowledge.node import EdgeType, KnowledgeNode, KnowledgeSource

_NODE_DATA_KEY = "data"


class KnowledgeGraph:
    """Directed graph storing facts, memories, and their relationships.

    Each node is a ``KnowledgeNode``; edges carry an ``EdgeType`` and
    optional metadata.  The graph lives in-memory during a session and
    can be serialised to / from a dict for save/load.

    Serialisation helpers live in ``knowledge.graph_serialization``.

    A side-index ``_witness_memory_index`` maps each witness NPC's
    UUID to the set of ``PERSONAL_EXPERIENCE`` memory node UUIDs they
    have a ``WITNESSED`` edge to. The index lets
    :meth:`personal_memories_for` answer per-NPC memory lookups in
    ``O(memories_for_npc)`` instead of walking every node in the
    graph on every Actor turn. ``WITNESSED`` is currently the only
    edge type emitted *from* NPC nodes (memory.py callers) and its
    target is always a ``PERSONAL_EXPERIENCE`` node — the index
    re-checks both before adding an entry, so a future caller that
    breaks this convention silently degrades coverage rather than
    poisoning the index.
    """

    def __init__(self) -> None:
        self.digraph: nx.DiGraph = nx.DiGraph()
        self._witness_memory_index: dict[UUID, set[UUID]] = {}

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def add_node(self, node: KnowledgeNode) -> UUID:
        """Add a knowledge node. Returns its UUID."""
        self.digraph.add_node(node.uuid, data=node)
        return node.uuid

    def register_actor_node(self, actor_id: UUID, label: str = "") -> None:
        """Register an NPC/actor as a graph node so memory edges can link to it.

        The node is added **without** a ``data`` payload so it stays invisible
        to ``all_nodes()`` and any ``KnowledgeQueryEngine`` queries — it exists
        purely as an endpoint for ``WITNESSED`` edges emitted by the memory
        manager. The ``label`` is stored as a networkx attribute for debugging
        and is never returned from knowledge queries.
        """
        self.digraph.add_node(actor_id, label=label)

    def get_node(self, node_id: UUID) -> KnowledgeNode | None:
        if node_id in self.digraph:
            return self.digraph.nodes[node_id].get(_NODE_DATA_KEY)
        return None

    def remove_node(self, node_id: UUID) -> None:
        if node_id not in self.digraph:
            return
        self._evict_from_witness_index(node_id)
        self.digraph.remove_node(node_id)

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    def add_edge(
        self,
        from_id: UUID,
        to_id: UUID,
        edge_type: EdgeType,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a directed edge.

        For ``WITNESSED`` edges, callers must ``add_node`` the target
        ``PERSONAL_EXPERIENCE`` node *before* this call so the
        witness-memory index can pick it up — the index is consulted
        on every Actor turn, and a missed entry silently degrades
        per-NPC memory coverage.
        """
        self.digraph.add_edge(from_id, to_id, edge_type=edge_type, **(metadata or {}))
        self._maybe_index_witness_edge(from_id, to_id, edge_type)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def all_nodes(self) -> list[KnowledgeNode]:
        """Return every node in the graph."""
        return [
            self.digraph.nodes[nid][_NODE_DATA_KEY]
            for nid in self.digraph.nodes
            if _NODE_DATA_KEY in self.digraph.nodes[nid]
        ]

    def get_edges_from(self, node_id: UUID) -> list[tuple[UUID, EdgeType]]:
        """Return (target_id, edge_type) for all outgoing edges."""
        if node_id not in self.digraph:
            return []
        return [
            (target, edge_attrs.get("edge_type", EdgeType.WITNESSED))
            for _, target, edge_attrs in self.digraph.out_edges(node_id, data=True)
        ]

    def personal_memories_for(self, npc_id: UUID) -> list[KnowledgeNode]:
        """Return every ``PERSONAL_EXPERIENCE`` node witnessed by *npc_id*.

        Backed by the witness-memory index, so this is
        ``O(memories_for_npc)`` instead of a full graph walk.
        """
        memory_ids = self._witness_memory_index.get(npc_id)
        if not memory_ids:
            return []
        memories: list[KnowledgeNode] = []
        for memory_id in memory_ids:
            node = self.get_node(memory_id)
            if node is not None:
                memories.append(node)
        return memories

    def rebuild_witness_memory_index(self) -> None:
        """Rebuild the witness-memory index from the current graph state.

        Used after deserialisation (``graph_serialization.from_dict``)
        and exposed for tests that mutate ``digraph`` directly.
        """
        rebuilt: dict[UUID, set[UUID]] = {}
        for source_id, target_id, edge_attrs in self.digraph.out_edges(data=True):
            if not self._is_witnessed_personal_memory(target_id, edge_attrs):
                continue
            rebuilt.setdefault(source_id, set()).add(target_id)
        self._witness_memory_index = rebuilt

    def _is_witnessed_personal_memory(self, target_id: UUID, edge_attrs: dict[str, Any]) -> bool:
        if edge_attrs.get("edge_type") != EdgeType.WITNESSED:
            return False
        target_node = self.get_node(target_id)
        return target_node is not None and target_node.source == KnowledgeSource.PERSONAL_EXPERIENCE

    # ------------------------------------------------------------------
    # Internal index maintenance
    # ------------------------------------------------------------------

    def _maybe_index_witness_edge(self, from_id: UUID, to_id: UUID, edge_type: EdgeType) -> None:
        if edge_type != EdgeType.WITNESSED:
            return
        target = self.get_node(to_id)
        if target is None or target.source != KnowledgeSource.PERSONAL_EXPERIENCE:
            return
        self._witness_memory_index.setdefault(from_id, set()).add(to_id)

    def _evict_from_witness_index(self, node_id: UUID) -> None:
        """Drop *node_id* from the index as both a witness key and a memory value."""
        self._witness_memory_index.pop(node_id, None)
        empty_witnesses: list[UUID] = []
        for witness_id, memory_ids in self._witness_memory_index.items():
            memory_ids.discard(node_id)
            if not memory_ids:
                empty_witnesses.append(witness_id)
        for witness_id in empty_witnesses:
            self._witness_memory_index.pop(witness_id, None)
