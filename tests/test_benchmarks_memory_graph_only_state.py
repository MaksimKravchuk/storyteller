"""Unit tests for the graph-only Marcus scenario state builder.

Verifies the single invariant that distinguishes this variant from the base
memory_follow_up_marcus scenario: Marcus's conversation_history is empty at
seed time while the KnowledgeGraph holds both facts via WITNESSED edges.
"""

from __future__ import annotations

import allure

from benchmarks.scenarios.memory_follow_up_marcus.state import _MARCUS_UUID
from benchmarks.scenarios.memory_follow_up_marcus_graph_only.state import build_state
from knowledge.node import EdgeType


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestMemoryGraphOnlyState:
    @allure.story("Graph-only scenario seed")
    @allure.title("Marcus's conversation_history is empty — no pre-seeded recall cues in the Actor prompt")
    def test_marcus_has_empty_conversation_history(self):
        marcus = build_state().game_state.npcs.get(_MARCUS_UUID)

        assert marcus is not None
        assert marcus.conversation_history == []

    @allure.story("Graph-only scenario seed")
    @allure.title("KnowledgeGraph contains at least two WITNESSED edges from Marcus's actor node")
    def test_graph_has_marcus_witnessed_edges(self):
        state = build_state().game_state
        witnessed = [
            tgt
            for tgt, edge_type in state.knowledge_graph.get_edges_from(_MARCUS_UUID)
            if edge_type == EdgeType.WITNESSED
        ]

        assert len(witnessed) >= 2

    @allure.story("Graph-only scenario seed")
    @allure.title("Two independent build_state calls produce separate objects — no shared mutable state")
    def test_build_state_independence(self):
        first = build_state()
        second = build_state()

        assert first.game_state is not second.game_state
        assert first.game_state.npcs.get(_MARCUS_UUID) is not second.game_state.npcs.get(_MARCUS_UUID)
