"""Diagnostics for the scene-consolidation edge-creation boundary.

The per-scene consolidation path hands NPC UUIDs derived from
``scene.npcs_present`` to ``MemoryManager``. When such a UUID was never
registered as a graph actor node, phase 1 silently drops the
``WITNESSED`` edge (orphan summary node) and phase 2 silently
auto-creates a phantom label-less actor node — two divergent silent
corruptions from one bad input. These are latent today (registration
sites are in sync) but must be loud so a future regression surfaces
instead of silently erasing an NPC's scene memory.

Also covers the phase-2 failure-log enrichment (I1) and the
"non-empty log, zero resolved witnesses" warning at the scene-swap
boundary (I2).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast import scene_swap
from knowledge import graph as kg_mod, node as _node, scene_consolidation
from knowledge.memory import MemoryEvent, MemoryManager
from llm.message import LLMResponse
from models import game_state as gs_mod, npc_card as npc_mod, scene as scene_mod
from models import scene_action_log as sal_mod, setting as setting_mod
from tests._uuid_helpers import make_uuid

KnowledgeGraph = kg_mod.KnowledgeGraph
GameState = gs_mod.GameState
NPCCard = npc_mod.NPCCard
Setting = setting_mod.Setting
ActorKind = sal_mod.ActorKind
SceneActionEntry = sal_mod.SceneActionEntry

pytestmark = [
    allure.epic("NPC short-term memory"),
    allure.feature("Consolidation diagnostics"),
]

_UNREGISTERED_NPC = make_uuid("npc-never-registered")


def _manager_with_summary() -> tuple[MemoryManager, KnowledgeGraph]:
    graph = KnowledgeGraph()
    llm = AsyncMock()
    llm.send_message = AsyncMock(
        return_value=LLMResponse(body="The NPC recalls a tense exchange.", model="stub", usage={}),
    )
    return MemoryManager(graph=graph, llm_client=llm), graph


def _errors(sink: list) -> list[str]:
    return [rec["message"] for rec in sink if rec["level"].name == "ERROR"]


def _warnings(sink: list) -> list[str]:
    return [rec["message"] for rec in sink if rec["level"].name == "WARNING"]


@allure.story("C1")
@allure.title("Phase-1 summary for an unregistered NPC logs an error instead of silently dropping the edge")
@pytest.mark.asyncio
async def test_unregistered_npc_summary_logs_error(loguru_sink) -> None:
    manager, graph = _manager_with_summary()

    await manager.summarize_interactions_batch([(_UNREGISTERED_NPC, "Player: hello\nNPC: hi")])

    # The summary node is still created (orphaned) — the regression we
    # guard against is the SILENT edge drop, so an ERROR must fire.
    errors = _errors(loguru_sink)
    assert any("unregistered" in msg and str(_UNREGISTERED_NPC) in msg for msg in errors)
    assert graph.get_edges_from(_UNREGISTERED_NPC) == []


@allure.story("C2")
@allure.title("Phase-2 shared node for an unregistered witness logs an error but still adds the edge")
@pytest.mark.asyncio
async def test_unregistered_witness_logs_error_but_preserves_edge(loguru_sink) -> None:
    manager, graph = _manager_with_summary()

    result = await manager.create_memory_from_event(
        MemoryEvent(
            event_description="A blade is drawn in the tavern.",
            witness_ids=[_UNREGISTERED_NPC],
            scope=_node.KnowledgeScope.LOCAL,
            location_id=make_uuid("loc"),
        ),
    )

    errors = _errors(loguru_sink)
    assert any("unregistered" in msg and str(_UNREGISTERED_NPC) in msg for msg in errors)
    # Behaviour is preserved: the node is created and the WITNESSED
    # edge still exists (auto-created phantom endpoint). Changing this
    # to a skip would drop real edges on DB rehydration, where actor
    # nodes are registered AFTER edges are loaded.
    assert result.canonical_id is not None
    assert (result.canonical_id, _node.EdgeType.WITNESSED) in graph.get_edges_from(_UNREGISTERED_NPC)


@allure.story("I1")
@allure.title("Phase-2 failure log carries enough context to identify the lost memory")
@pytest.mark.asyncio
async def test_significant_phase_failure_log_is_actionable(loguru_sink) -> None:
    manager = AsyncMock(spec=MemoryManager)
    manager.create_memory_from_event = AsyncMock(side_effect=RuntimeError("graph write failed"))
    loc = make_uuid("loc-forum")
    request = scene_consolidation.SceneConsolidationRequest(
        entries=[
            SceneActionEntry(
                actor_kind=ActorKind.NPC,
                actor_uuid=make_uuid("marcus"),
                actor_name="Marcus",
                action_type="ATTACK",
                description="Marcus lunges at Livia with a dagger across the forum.",
                target_name="Livia",
                game_clock=7.5,
                significant=True,
            ),
        ],
        present_npc_uuids=[make_uuid("witness")],
        game_time=7.5,
        location_id=loc,
        player_subject_id=make_uuid("player"),
    )

    await scene_consolidation._significant_phase(manager, request)

    errors = _errors(loguru_sink)
    assert errors, "a failed significant-event write must log an ERROR"
    failure = errors[0]
    assert "ATTACK" in failure
    assert "Livia" in failure
    assert str(loc) in failure
    assert "7.5" in failure
    assert "Marcus lunges at Livia" in failure


@allure.story("I1")
@allure.title("A runaway description is truncated in the failure log, not dumped whole")
@pytest.mark.asyncio
async def test_significant_phase_failure_log_truncates_description(loguru_sink) -> None:
    manager = AsyncMock(spec=MemoryManager)
    manager.create_memory_from_event = AsyncMock(side_effect=RuntimeError("graph write failed"))
    long_desc = "X" * 500
    request = scene_consolidation.SceneConsolidationRequest(
        entries=[
            SceneActionEntry(
                actor_kind=ActorKind.NPC,
                actor_uuid=make_uuid("marcus"),
                actor_name="Marcus",
                action_type="ATTACK",
                description=long_desc,
                game_clock=1.0,
                significant=True,
            ),
        ],
        present_npc_uuids=[make_uuid("witness")],
        game_time=1.0,
        location_id=make_uuid("loc"),
        player_subject_id=make_uuid("player"),
    )

    await scene_consolidation._significant_phase(manager, request)

    failure = _errors(loguru_sink)[0]
    cap = scene_consolidation._DESC_PREVIEW_CHARS
    assert "X" * cap in failure
    assert "X" * (cap + 1) not in failure


def _gs_with_log_no_present_npcs() -> tuple[GameState, scene_mod.Scene]:
    gs = GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=KnowledgeGraph(),
    )
    # An NPC exists but is NOT in npcs_present, so no witness resolves
    # at swap even though the log is non-empty.
    marcus = NPCCard(name="Marcus", occupation="guard")
    marcus.uuid = make_uuid("marcus")
    gs.npcs[marcus.uuid] = marcus
    outgoing = scene_mod.Scene(location_id=make_uuid("loc-old"), description="An empty plaza.", npcs_present=[])
    gs.current_scene = outgoing
    gs.scene_action_log.append(
        SceneActionEntry(
            actor_kind=ActorKind.PLAYER,
            actor_uuid=gs.player.uuid,
            actor_name="Player",
            action_type="ATTACK",
            description="I smash the shrine.",
            game_clock=3.0,
            significant=True,
        ),
    )
    return gs, outgoing


@allure.story("I2")
@allure.title("A non-empty log dropped because zero witnesses resolved logs a warning")
@pytest.mark.asyncio
async def test_non_empty_log_zero_witnesses_warns(loguru_sink) -> None:
    gs, outgoing = _gs_with_log_no_present_npcs()
    manager = AsyncMock(spec=MemoryManager)

    await scene_swap.consolidate_outgoing_scene(manager, gs, outgoing)

    warnings = _warnings(loguru_sink)
    assert any("1" in msg and str(outgoing.location_id) in msg for msg in warnings)
    manager.summarize_interactions_batch.assert_not_awaited()


@allure.story("I2")
@allure.title("An empty log is a silent no-op — no warning")
@pytest.mark.asyncio
async def test_empty_log_no_warning(loguru_sink) -> None:
    gs, outgoing = _gs_with_log_no_present_npcs()
    gs.scene_action_log = []
    manager = AsyncMock(spec=MemoryManager)

    await scene_swap.consolidate_outgoing_scene(manager, gs, outgoing)

    assert _warnings(loguru_sink) == []
