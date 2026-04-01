"""Knowledge graph — networkx-backed storage for all world knowledge and NPC memories."""

from __future__ import annotations

from typing import Any

import networkx as nx

from knowledge.node import EdgeType, KnowledgeNode, KnowledgeScope


_NODE_DATA_KEY = "data"


class KnowledgeGraph:
    """Directed graph storing facts, memories, and their relationships.

    Each node is a ``KnowledgeNode``; edges carry an ``EdgeType`` and
    optional metadata.  The graph lives in-memory during a session and
    can be serialised to / from a dict for save/load.
    """

    def __init__(self) -> None:
        self._graph: nx.DiGraph = nx.DiGraph()

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def add_node(self, node: KnowledgeNode) -> str:
        """Add a knowledge node. Returns its UUID."""
        self._graph.add_node(node.uuid, data=node)
        return node.uuid

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        if node_id in self._graph:
            return self._graph.nodes[node_id].get(_NODE_DATA_KEY)
        return None

    def remove_node(self, node_id: str) -> None:
        if node_id in self._graph:
            self._graph.remove_node(node_id)

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
        self._graph.add_edge(from_id, to_id, edge_type=edge_type, **(metadata or {}))

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def all_nodes(self) -> list[KnowledgeNode]:
        """Return every node in the graph."""
        return [
            self._graph.nodes[nid][_NODE_DATA_KEY]
            for nid in self._graph.nodes
            if _NODE_DATA_KEY in self._graph.nodes[nid]
        ]

    def query_by_scope(self, max_scope: KnowledgeScope) -> list[KnowledgeNode]:
        """Return all nodes whose scope is at or below ``max_scope``."""
        return [node for node in self.all_nodes() if node.scope <= max_scope]

    def query_by_tags(self, tags: list[str]) -> list[KnowledgeNode]:
        """Return nodes that have at least one matching tag."""
        tag_set = set(tags)
        return [node for node in self.all_nodes() if tag_set & set(node.tags)]

    def query_by_location(self, location_id: str) -> list[KnowledgeNode]:
        """Return nodes associated with a specific location."""
        return [node for node in self.all_nodes() if node.location_id == location_id]

    def get_related(self, node_id: str, depth: int = 2) -> list[KnowledgeNode]:
        """BFS traversal: find nodes within ``depth`` hops of ``node_id``."""
        if node_id not in self._graph:
            return []
        visited: set[str] = set()
        # Use networkx BFS with depth limit
        for _, target in nx.bfs_edges(self._graph, node_id, depth_limit=depth):
            visited.add(target)
        nodes = self._graph.nodes
        return [nodes[nid][_NODE_DATA_KEY] for nid in visited if _NODE_DATA_KEY in nodes[nid]]

    def get_edges_from(self, node_id: str) -> list[tuple[str, EdgeType]]:
        """Return (target_id, edge_type) for all outgoing edges."""
        if node_id not in self._graph:
            return []
        return [
            (target, edge_attrs.get("edge_type", EdgeType.RELATED_TO))
            for _, target, edge_attrs in self._graph.out_edges(node_id, data=True)
        ]

    @property
    def node_count(self) -> int:
        return self._graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self._graph.number_of_edges()

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise the graph for save/load."""
        return nx.node_link_data(self._graph)

    @classmethod
    def from_dict(cls, graph_dict: dict) -> KnowledgeGraph:
        """Restore a graph from serialised data."""
        kg = cls()
        kg._graph = nx.node_link_graph(graph_dict)
        return kg
