"""Resilience of scene-end consolidation's two phases.

``_significant_phase`` fans the per-event long-term writes out via
``asyncio.gather``. Without ``return_exceptions=True`` the first failing
``create_memory_from_event`` aborts the whole phase while its siblings
keep running — a partial graph write that is then re-attempted (and
double-written) on the next swap. The phase must instead let the
surviving writes complete and log the failures.

Phase 1 (the per-NPC summary) is a single LLM batch call. If it
raises, the scene-swap caller still wipes the action log, so a
propagated phase-1 error would skip the resilient significant-event
phase and permanently lose every combat/intimidation/witness node.
Phase 1 must be swallowed (logged) so phase 2 still runs; cooperative
cancellation must still propagate.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import allure
import pytest

from knowledge import scene_consolidation
from knowledge.memory import MemoryManager
from models.scene_action_log import ActorKind, SceneActionEntry
from tests._uuid_helpers import make_uuid

pytestmark = [
    allure.epic("NPC short-term memory"),
    allure.feature("Scene consolidation resilience"),
]


def _significant_entry(description: str) -> SceneActionEntry:
    return SceneActionEntry(
        actor_kind=ActorKind.NPC,
        actor_uuid=make_uuid(description),
        actor_name="Marcus",
        action_type="ATTACK",
        description=description,
        game_clock=1.0,
        significant=True,
    )


@allure.story("Phase 2")
@allure.title("I1 — one failing significant-event write does not abort the surviving writes")
@pytest.mark.asyncio
async def test_significant_phase_tolerates_one_failed_write(loguru_sink) -> None:
    manager = AsyncMock(spec=MemoryManager)
    manager.create_memory_from_event = AsyncMock(
        side_effect=[RuntimeError("graph write failed"), None, None],
    )
    request = scene_consolidation.SceneConsolidationRequest(
        entries=[_significant_entry("a"), _significant_entry("b"), _significant_entry("c")],
        present_npc_uuids=[make_uuid("witness")],
        game_time=1.0,
        location_id=make_uuid("loc"),
        player_subject_id=make_uuid("player"),
    )

    await scene_consolidation._significant_phase(manager, request)

    assert manager.create_memory_from_event.await_count == 3
    assert any(rec["level"].name == "ERROR" for rec in loguru_sink)


@allure.story("Phase 2")
@allure.title("I1 — cooperative cancellation propagates, it is not swallowed as a log line")
@pytest.mark.asyncio
async def test_significant_phase_propagates_cancellation() -> None:
    manager = AsyncMock(spec=MemoryManager)
    manager.create_memory_from_event = AsyncMock(side_effect=asyncio.CancelledError())
    request = scene_consolidation.SceneConsolidationRequest(
        entries=[_significant_entry("a")],
        present_npc_uuids=[make_uuid("witness")],
        game_time=1.0,
        location_id=make_uuid("loc"),
        player_subject_id=make_uuid("player"),
    )

    with pytest.raises(asyncio.CancelledError):
        await scene_consolidation._significant_phase(manager, request)


def _request_with_present_actor(description: str) -> scene_consolidation.SceneConsolidationRequest:
    """Request whose lone significant entry is authored by the present NPC.

    The present NPC must appear in the log or phase 1 short-circuits
    before the summariser call (per-NPC presence scoping), so the
    failure path under test would never be exercised.
    """
    return scene_consolidation.SceneConsolidationRequest(
        entries=[_significant_entry(description)],
        present_npc_uuids=[make_uuid(description)],
        game_time=1.0,
        location_id=make_uuid("loc"),
        player_subject_id=make_uuid("player"),
    )


@allure.story("Phase 1")
@allure.title("A phase-1 LLM failure is swallowed so the significant-event phase still runs")
@pytest.mark.asyncio
async def test_summary_phase_failure_does_not_skip_significant_phase(loguru_sink) -> None:
    manager = AsyncMock(spec=MemoryManager)
    manager.summarize_interactions_batch = AsyncMock(side_effect=RuntimeError("LLM timeout"))
    manager.create_memory_from_event = AsyncMock(return_value=None)

    # Must NOT raise: the scene-swap caller wipes the log right after.
    await scene_consolidation.consolidate_scene(manager, _request_with_present_actor("a"))

    manager.summarize_interactions_batch.assert_awaited_once()
    manager.create_memory_from_event.assert_awaited_once()
    assert any(rec["level"].name == "ERROR" for rec in loguru_sink)


@allure.story("Phase 1")
@allure.title("Phase-1 cancellation propagates and the significant-event phase does not run")
@pytest.mark.asyncio
async def test_summary_phase_cancellation_propagates_and_skips_phase_two() -> None:
    manager = AsyncMock(spec=MemoryManager)
    manager.summarize_interactions_batch = AsyncMock(side_effect=asyncio.CancelledError())
    manager.create_memory_from_event = AsyncMock(return_value=None)

    with pytest.raises(asyncio.CancelledError):
        await scene_consolidation.consolidate_scene(manager, _request_with_present_actor("a"))

    manager.create_memory_from_event.assert_not_awaited()
