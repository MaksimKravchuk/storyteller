"""Charge stamping at the three PERSONAL_EXPERIENCE construction sites."""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from knowledge import charge
from knowledge.graph import KnowledgeGraph
from knowledge.memory import MemoryEvent, MemoryManager
from knowledge.memory_slots import EMPTY_SLOTS
from knowledge.node import KnowledgeNode, KnowledgeScope, KnowledgeSource
from llm.message import LLMResponse
from tests._uuid_helpers import make_uuid

pytestmark = [
    allure.epic("Memory & Persistence"),
    allure.feature("Memory manager"),
    allure.story("Emotional charge stamping"),
]

_W1 = make_uuid("witness-1")
_SUMMARY_TEXT = "The traveller helped the merchant."


def _make_manager() -> tuple[MemoryManager, KnowledgeGraph]:
    graph = KnowledgeGraph()
    llm = AsyncMock()
    llm.send_message = AsyncMock(return_value=LLMResponse(body=_SUMMARY_TEXT, model="stub", usage={}))
    return MemoryManager(graph=graph, llm_client=llm), graph


def _personal_nodes(graph: KnowledgeGraph) -> list[KnowledgeNode]:
    return [node for node in graph.all_nodes() if node.source == KnowledgeSource.PERSONAL_EXPERIENCE]


@pytest.mark.asyncio
@allure.title("The shared personal node carries the stamped charge")
async def test_shared_personal_node_carries_charge() -> None:
    manager, graph = _make_manager()
    graph.register_actor_node(_W1)
    await manager.create_memory_from_event(
        MemoryEvent(
            event_description="A clash",
            witness_ids=[_W1],
            scope=KnowledgeScope.LOCAL,
            valence=charge.COMBAT.base_valence,
            charge_intensity=charge.COMBAT.base_intensity,
            charge_category=charge.COMBAT.category,
        ),
    )
    node = graph.personal_memories_for(_W1)[0]
    assert node.valence == pytest.approx(charge.COMBAT.base_valence)
    assert node.charge_intensity == pytest.approx(charge.COMBAT.base_intensity)
    assert node.charge_category == charge.VIOLENCE


@pytest.mark.asyncio
@allure.title("The broadcast node stays neutral while the witness copy is charged")
async def test_broadcast_node_is_neutral_while_witness_copy_is_charged() -> None:
    manager, graph = _make_manager()
    graph.register_actor_node(_W1)
    result = await manager.create_memory_from_event(
        MemoryEvent(
            event_description="A public execution",
            witness_ids=[_W1],
            scope=KnowledgeScope.CITY,  # broadcast path
            valence=charge.COMBAT.base_valence,
            charge_intensity=charge.COMBAT.base_intensity,
            charge_category=charge.COMBAT.category,
        ),
    )
    assert result.canonical_id is not None
    broadcast = graph.get_node(result.canonical_id)
    assert broadcast is not None
    assert broadcast.source != KnowledgeSource.PERSONAL_EXPERIENCE
    assert broadcast.valence == 0
    assert broadcast.charge_intensity == 0
    assert broadcast.charge_category == ""
    witness_copy = graph.personal_memories_for(_W1)[0]
    assert witness_copy.charge_intensity == pytest.approx(charge.COMBAT.base_intensity)


@pytest.mark.asyncio
@allure.title("A dialogue summary carries neutral charge (felt charge rides event memories)")
async def test_dialogue_summary_is_neutral() -> None:
    manager, graph = _make_manager()
    graph.register_actor_node(_W1)
    await manager.summarize_interactions_batch([(_W1, "player: hi\nnpc: hello")])
    node = _personal_nodes(graph)[0]
    assert node.charge_intensity == pytest.approx(0)
    assert node.charge_category == ""


@pytest.mark.asyncio
@allure.title("A retaliation summary upgrades the charge of a deduped neutral dialogue summary")
async def test_retaliation_charge_upgrades_deduped_dialogue_summary() -> None:
    """Regression: when an aggressive turn writes the neutral dialogue summary
    first and then a near-identical retaliation summary for the same NPC, dedup
    must not leave the memory inert — it upgrades the surviving node's charge so
    the emotional-memory subsystem still sees the grudge.
    """
    manager, graph = _make_manager()  # the stub returns the same text for both calls
    graph.register_actor_node(_W1)

    # 1) neutral dialogue summary lands first
    await manager.summarize_interactions_batch([(_W1, "player squares up to the guard")])
    # 2) near-identical retaliation summary for the SAME NPC is deduped, not dropped
    await manager.summarize_interactions_batch([(_W1, "[retaliation] ...", EMPTY_SLOTS, charge.RETALIATION)])

    nodes = _personal_nodes(graph)
    assert len(nodes) == 1  # dedup held — no redundant node
    assert nodes[0].charge_intensity == pytest.approx(charge.RETALIATION.base_intensity)
    assert nodes[0].charge_category == charge.RETALIATION_CATEGORY
    assert nodes[0].valence == pytest.approx(charge.RETALIATION.base_valence)
