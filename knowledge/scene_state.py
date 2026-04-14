"""Scene-state persistence helpers (KER-13).

Persistent deltas produced by ``INTERACT``-with-object turns (broken
windows, toppled statues, lit torches) live in the knowledge graph as
``KnowledgeNode``s tagged ``scene_state``. Storing them in the graph
rather than on a scene-specific side table keeps world state in one
place — the same place the Dramaturge already consults when checking
for contradictions — and lets the Scene Builder re-query them when
rebuilding a location the player left and later returned to.

The nodes are:

* ``scope=LOCAL`` — only visible at the originating location.
* ``source=FACT`` — this is objectively what the world looks like now.
* ``canon=SESSION`` — player-caused, never overridden by historical
  Wikipedia facts.
* ``location_id`` — the scene where the delta was emitted, used as the
  query key.
* ``tags`` — always include ``"scene_state"`` plus the ``location_id``
  for fast tag-based filtering.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from knowledge.node import (
    CanonSource,
    KnowledgeNode,
    KnowledgeScope,
    KnowledgeSource,
)
from models.game_state import INITIAL_GAME_CLOCK

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph

SCENE_STATE_TAG = "scene_state"


def _is_scene_state_for_location(node: KnowledgeNode, location_id: str) -> bool:
    """Return True when ``node`` is a scene-state delta for ``location_id``."""
    return node.location_id == location_id and SCENE_STATE_TAG in node.tags


def record_scene_delta(
    graph: KnowledgeGraph,
    *,
    location_id: str,
    delta_text: str,
    game_time: float = INITIAL_GAME_CLOCK,
) -> str:
    """Write a persistent scene-state delta for ``location_id``.

    Returns the UUID of the created node so callers (primarily the
    object-interaction handler) can thread it into witness memory
    edges or downstream logging.
    """
    node = KnowledgeNode(
        text=delta_text,
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.FACT,
        canon=CanonSource.SESSION,
        location_id=location_id,
        timestamp=game_time,
        tags=[SCENE_STATE_TAG, location_id],
    )
    return graph.add_node(node)


def query_scene_deltas(
    graph: KnowledgeGraph,
    location_id: str,
) -> list[KnowledgeNode]:
    """Return every scene-state delta recorded for ``location_id``.

    Nodes are filtered by both the ``scene_state`` tag and the
    ``location_id`` field so ambient memory nodes that happen to carry
    a location id do not leak into the scene rebuild prompt.
    """
    return [node for node in graph.all_nodes() if _is_scene_state_for_location(node, location_id)]


def all_scene_deltas(graph: KnowledgeGraph) -> dict[str, list[str]]:
    """Return every ``scene_state`` delta grouped by ``location_id``.

    Used by :class:`cast.scene_builder.SceneBuilder` when building the
    ``persistent_world_changes`` section of its prompt — the Scene
    Builder does not know the target location deterministically before
    the LLM call, so it injects every known delta and relies on the
    LLM to apply only those matching the scene it emits.
    """
    grouped: dict[str, list[str]] = {}
    for node in graph.all_nodes():
        if SCENE_STATE_TAG not in node.tags or not node.location_id:
            continue
        grouped.setdefault(node.location_id, []).append(node.text)
    return grouped
