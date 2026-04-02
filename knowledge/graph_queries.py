"""Query functions for the knowledge graph — extracted from KnowledgeGraph class."""

from __future__ import annotations

from typing import TYPE_CHECKING

import networkx as nx

from knowledge.node import KnowledgeNode, KnowledgeScope

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph

_NODE_DATA_KEY = "data"


def query_by_scope(graph: KnowledgeGraph, max_scope: KnowledgeScope) -> list[KnowledgeNode]:
    """Return all nodes whose scope is at or below ``max_scope``."""
    return [node for node in graph.all_nodes() if node.scope <= max_scope]


def query_by_tags(graph: KnowledgeGraph, tags: list[str]) -> list[KnowledgeNode]:
    """Return nodes that have at least one matching tag."""
    tag_set = set(tags)
    return [node for node in graph.all_nodes() if tag_set & set(node.tags)]


def query_by_location(graph: KnowledgeGraph, location_id: str) -> list[KnowledgeNode]:
    """Return nodes associated with a specific location."""
    return [node for node in graph.all_nodes() if node.location_id == location_id]


def get_related(graph: KnowledgeGraph, node_id: str, depth: int = 2) -> list[KnowledgeNode]:
    """BFS traversal: find nodes within ``depth`` hops of ``node_id``."""
    if node_id not in graph.digraph:
        return []
    visited: set[str] = set()
    for _, target in nx.bfs_edges(graph.digraph, node_id, depth_limit=depth):
        visited.add(target)
    raw_nodes = graph.digraph.nodes
    return [raw_nodes[nid][_NODE_DATA_KEY] for nid in visited if _NODE_DATA_KEY in raw_nodes[nid]]
