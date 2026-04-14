"""Populate a KnowledgeGraph from Setting data."""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph
from knowledge.node import CanonSource, KnowledgeNode, KnowledgeScope, KnowledgeSource
from models.setting import Setting


def _format_person_content(person: dict) -> str:
    name = person.get("name", "Unknown")
    role = person.get("role", "")
    description = person.get("description", "")
    return f"{name}: {role}. {description}"


def _format_event_content(event: dict) -> str:
    name = event.get("name", "Unknown event")
    date = event.get("date", "")
    description = event.get("description", "")
    return f"{name} ({date}): {description}"


def _format_location_content(loc: dict) -> str:
    name = loc.get("name", "Unknown place")
    loc_type = loc.get("type", "")
    description = loc.get("description", "")
    return f"{name} ({loc_type}): {description}"


def _add_node(
    graph: KnowledgeGraph,
    node_content: str,
    scope: KnowledgeScope,
    required_education: int = 0,
    tags: list[str] | None = None,
) -> None:
    """Add a FACT knowledge node to the graph."""
    graph.add_node(
        KnowledgeNode(
            text=node_content,
            scope=scope,
            source=KnowledgeSource.FACT,
            canon=CanonSource.HISTORICAL,
            required_education=required_education,
            tags=tags or [],
        )
    )


def _add_persons_and_events(graph: KnowledgeGraph, setting: Setting) -> None:
    """Add key persons and events from setting to knowledge graph."""
    for person in setting.key_persons:
        _add_node(
            graph,
            _format_person_content(person),
            KnowledgeScope.COUNTRY,
            required_education=3,
            tags=["person", "politics"],
        )
    for event in setting.key_events:
        _add_node(
            graph,
            _format_event_content(event),
            KnowledgeScope.REGION,
            required_education=2,
            tags=["event", "history"],
        )


def _add_locations_and_culture(graph: KnowledgeGraph, setting: Setting) -> None:
    """Add locations, traditions, technologies, and social structure."""
    for loc in setting.locations:
        _add_node(
            graph,
            _format_location_content(loc),
            KnowledgeScope.CITY,
            tags=["location"],
        )
    for tradition in setting.traditions:
        _add_node(graph, tradition, KnowledgeScope.REGION, tags=["tradition", "culture"])
    for tech in setting.technologies:
        _add_node(
            graph,
            tech,
            KnowledgeScope.REGION,
            required_education=1,
            tags=["technology"],
        )
    if setting.social_structure:
        _add_node(
            graph,
            setting.social_structure,
            KnowledgeScope.COUNTRY,
            required_education=2,
            tags=["society", "social_structure"],
        )


def populate_graph_from_setting(graph: KnowledgeGraph, setting: Setting) -> None:
    """Convert Setting data into knowledge graph nodes."""
    graph.add_node(
        KnowledgeNode(
            text=setting.summary,
            scope=KnowledgeScope.WORLD,
            source=KnowledgeSource.FACT,
            canon=CanonSource.HISTORICAL,
            tags=["setting", "overview"],
        )
    )
    _add_persons_and_events(graph, setting)
    _add_locations_and_culture(graph, setting)
