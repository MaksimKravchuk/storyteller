"""Per-NPC failure isolation in ``MemoryManager.summarize_interactions_batch``.

The batch fans one summariser LLM call out per present NPC. It feeds
scene-end consolidation, after which the scene-swap caller wipes the
action log — so an all-or-nothing ``asyncio.gather`` would let one
NPC's timeout / rate-limit / parse error permanently erase every
present NPC's scene memory. The batch must isolate the failure, keep
the survivors, and log the loss; cooperative cancellation must still
propagate instead of being swallowed as a log line.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import allure
import pytest

from knowledge.graph import KnowledgeGraph
from knowledge.memory import MemoryManager
from knowledge.node import KnowledgeSource
from llm.message import LLMResponse
from tests._uuid_helpers import make_uuid

pytestmark = [
    allure.epic("Memory & Persistence"),
    allure.feature("Summary batch resilience"),
]

_SUMMARY_TEXT = "A heated argument over silver."
_GOOD_NPC = make_uuid("npc-good")
_BAD_NPC = make_uuid("npc-bad")


def _fail_summary_on_bad_pair(messages, **_kwargs) -> LLMResponse:
    """Summariser stub: raise for the pair whose transcript contains BAD."""
    if "BAD" in messages[0].body:
        raise RuntimeError("LLM timeout for one NPC")
    return LLMResponse(body=_SUMMARY_TEXT, model="stub", usage={})


def _make_manager() -> tuple[MemoryManager, KnowledgeGraph, AsyncMock]:
    graph = KnowledgeGraph()
    llm = AsyncMock()
    return MemoryManager(graph=graph, llm_client=llm), graph, llm


@allure.story("summarize_interactions_batch")
@allure.title("one NPC's summariser failure does not destroy every other present NPC's summary")
@pytest.mark.asyncio
async def test_summarize_batch_isolates_one_failed_pair(loguru_sink) -> None:
    manager, graph, llm = _make_manager()
    graph.register_actor_node(_GOOD_NPC, label="Marcus")
    graph.register_actor_node(_BAD_NPC, label="Cassia")
    llm.send_message = AsyncMock(side_effect=_fail_summary_on_bad_pair)

    await manager.summarize_interactions_batch([(_GOOD_NPC, "GOOD"), (_BAD_NPC, "BAD")])

    memory_nodes = [n for n in graph.all_nodes() if n.source == KnowledgeSource.PERSONAL_EXPERIENCE]
    assert len(memory_nodes) == 1
    assert graph.get_edges_from(_GOOD_NPC)[0][0] == memory_nodes[0].uuid
    assert any(rec["level"].name == "ERROR" for rec in loguru_sink)


@allure.story("summarize_interactions_batch")
@allure.title("cooperative cancellation propagates instead of being swallowed as a log line")
@pytest.mark.asyncio
async def test_summarize_batch_propagates_cancellation() -> None:
    manager, _graph, llm = _make_manager()
    llm.send_message = AsyncMock(side_effect=asyncio.CancelledError())

    with pytest.raises(asyncio.CancelledError):
        await manager.summarize_interactions_batch([(_GOOD_NPC, "x")])
