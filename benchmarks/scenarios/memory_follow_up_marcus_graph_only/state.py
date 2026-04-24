"""Seed state builder for the graph-only Marcus memory follow-up scenario.

Facts are stored exclusively in the KnowledgeGraph — NPCCard.conversation_history
is left empty so the Actor prompt contains no pre-seeded recall cues.  The LLM
must retrieve facts through the actual memory-retrieval pipeline.
"""

from __future__ import annotations

from benchmarks.harness.types._scenarios import ScenarioState
from benchmarks.scenarios.memory_follow_up_marcus.state import (
    _make_location,
    _make_marcus_base,
    _make_scene,
    _make_setting,
    _seed_marcus_memories,
)
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState, PlayerState


def build_state() -> ScenarioState:
    """Construct the seed :class:`GameState` for the graph-only variant."""
    graph = KnowledgeGraph()
    marcus = _make_marcus_base()

    location = _make_location()
    _seed_marcus_memories(graph, marcus.uuid, location.uuid)
    marcus.location_id = location.uuid

    game_state = GameState(
        setting=_make_setting(),
        knowledge_graph=graph,
        player=PlayerState(name="Traveller", location_id=location.uuid),
    )
    game_state.locations[location.uuid] = location
    game_state.npcs[marcus.uuid] = marcus
    game_state.current_scene = _make_scene(location.uuid, marcus.uuid)
    game_state.game_clock = 10.0
    game_state.game_time = "morning"
    return ScenarioState(game_state=game_state, events=[])
