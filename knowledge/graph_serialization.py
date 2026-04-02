"""Serialization and stat functions for KnowledgeGraph — extracted from the class."""

from __future__ import annotations

from typing import TYPE_CHECKING

import networkx as nx

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph


def node_count(graph: KnowledgeGraph) -> int:
    """Return the number of nodes in the graph."""
    return graph.digraph.number_of_nodes()


def edge_count(graph: KnowledgeGraph) -> int:
    """Return the number of edges in the graph."""
    return graph.digraph.number_of_edges()


def to_dict(graph: KnowledgeGraph) -> dict:
    """Serialise the graph for save/load."""
    return nx.node_link_data(graph.digraph)


def from_dict(graph_dict: dict) -> KnowledgeGraph:
    """Restore a KnowledgeGraph from serialised data."""
    from knowledge.graph import KnowledgeGraph

    kg = KnowledgeGraph()
    kg.digraph = nx.node_link_graph(graph_dict)
    return kg
