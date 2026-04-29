"""Knowledge graph — networkx-backed storage for all world knowledge and NPC memories."""

from __future__ import annotations

from typing import Any

import networkx as nx

from knowledge.node import EdgeType, KnowledgeNode

_NODE_DATA_KEY = "data"


class KnowledgeGraph:
    """Directed graph storing facts, memories, and their relationships.

    Each node is a ``KnowledgeNode``; edges carry an ``EdgeType`` and
    optional metadata.  The graph lives in-memory during a session and
    can be serialised to / from a dict for save/load.

    Serialisation helpers live in ``knowledge.graph_serialization``.
    """

    def __init__(self) -> None:
        self.digraph: nx.DiGraph = nx.DiGraph()

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def add_node(self, node: KnowledgeNode) -> str:
        """Add a knowledge node. Returns its UUID."""
        self.digraph.add_node(node.uuid, data=node)
        return node.uuid

    def register_actor_node(self, actor_id: str, label: str = "") -> None:
        """Register an NPC/actor as a graph node so memory edges can link to it.

        The node is added **without** a ``data`` payload so it stays invisible
        to ``all_nodes()`` and any ``KnowledgeQueryEngine`` queries — it exists
        purely as an endpoint for ``WITNESSED`` edges emitted by the memory
        manager. The ``label`` is stored as a networkx attribute for debugging
        and is never returned from knowledge queries.
        """
        self.digraph.add_node(actor_id, label=label)

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        if node_id in self.digraph:
            return self.digraph.nodes[node_id].get(_NODE_DATA_KEY)
        return None

    def remove_node(self, node_id: str) -> None:
        if node_id in self.digraph:
            self.digraph.remove_node(node_id)

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    def add_edge(
        self,
        from_id: str,
        to_id: str,
        edge_type: EdgeType,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.digraph.add_edge(from_id, to_id, edge_type=edge_type, **(metadata or {}))

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

    def get_edges_from(self, node_id: str) -> list[tuple[str, EdgeType]]:
        """Return (target_id, edge_type) for all outgoing edges."""
        if node_id not in self.digraph:
            return []
        return [
            (target, edge_attrs.get("edge_type", EdgeType.RELATED_TO))
            for _, target, edge_attrs in self.digraph.out_edges(node_id, data=True)
        ]
