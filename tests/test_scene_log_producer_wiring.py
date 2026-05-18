"""Producer-side wiring for the per-scene action log.

The combat and object-witness hooks write their own long-term node and
must also drop a scene-log entry flagged ``already_persisted=True`` so
scene-end consolidation (phase 2) does not double-write the same event.
The dialogue hook must append exactly one TALK entry per work item.
These contracts were only covered via the standalone append helper, not
at the real call sites — this module closes that gap.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import allure
import pytest

from cast._npc_combat_memory import CombatEvent, persist_combat_memory
from cast._npc_outcome import OutcomeKind
from cast.director_dialogue import _record_dialogue_in_scene_log
from cast.director_object_witness import emit_witness_memories
from knowledge.memory import MemoryManager
from models.npc_card import NPCCard
from models.scene_action_log import ActorKind
from tests.director_helpers import make_game_state, make_uuid

pytestmark = [
    allure.epic("NPC short-term memory"),
    allure.feature("Scene-log producer wiring"),
]


@allure.story("Combat de-dup")
@allure.title("persist_combat_memory leaves one already_persisted COMBAT_WITNESS scene-log entry")
@pytest.mark.asyncio
async def test_combat_hook_appends_already_persisted_event() -> None:
    actor = NPCCard(name="Brutus", occupation="legionary")
    target = NPCCard(name="Marcus", occupation="merchant")
    game_state = make_game_state()
    memory_manager = AsyncMock(spec=MemoryManager)

    await persist_combat_memory(
        memory_manager,
        CombatEvent(actor=actor, target=target, new_value="wounded", kind=OutcomeKind.PHYSICAL),
        game_state,
    )

    memory_manager.create_memory_from_event.assert_awaited_once()
    events = [entry for entry in game_state.scene_action_log if entry.actor_kind == ActorKind.EVENT]
    assert len(events) == 1
    assert events[0].action_type == "COMBAT_WITNESS"
    assert events[0].metadata.get("already_persisted") is True
    assert events[0].target_uuid == target.uuid
    assert "Brutus" in events[0].description
    assert "wounded" in events[0].description


@allure.story("Witness de-dup")
@allure.title("emit_witness_memories leaves one already_persisted WITNESS scene-log entry")
@pytest.mark.asyncio
async def test_witness_hook_appends_already_persisted_event() -> None:
    game_state = make_game_state()
    memory_manager = AsyncMock(spec=MemoryManager)
    memory_manager.create_memory_from_event = AsyncMock(
        return_value=MagicMock(canonical_id=make_uuid("fact")),
    )

    await emit_witness_memories(
        memory_manager,
        game_state,
        [make_uuid("guard")],
        "The front shutter hangs splintered and broken.",
    )

    memory_manager.create_memory_from_event.assert_awaited_once()
    events = [entry for entry in game_state.scene_action_log if entry.actor_kind == ActorKind.EVENT]
    assert len(events) == 1
    assert events[0].action_type == "WITNESS"
    assert events[0].metadata.get("already_persisted") is True


@allure.story("Witness de-dup")
@allure.title("A no-op witness broadcast (no witnesses) writes no node and appends nothing")
@pytest.mark.asyncio
async def test_witness_hook_no_witnesses_is_a_no_op() -> None:
    game_state = make_game_state()
    memory_manager = AsyncMock(spec=MemoryManager)

    await emit_witness_memories(memory_manager, game_state, [], "ignored")

    memory_manager.create_memory_from_event.assert_not_awaited()
    assert game_state.scene_action_log == []


@allure.story("Dialogue per-target")
@allure.title("_record_dialogue_in_scene_log appends one TALK entry per work item, attributed to its NPC")
def test_dialogue_hook_appends_one_entry_per_work_item() -> None:
    game_state = make_game_state()
    npc_a = NPCCard(name="Cassius", occupation="guard")
    npc_a.uuid = make_uuid("dlg-a")
    npc_b = NPCCard(name="Drusus", occupation="guard")
    npc_b.uuid = make_uuid("dlg-b")
    dialogue_entries = [
        {"response": "State your business."},
        {"response": "Move along, stranger."},
    ]

    _record_dialogue_in_scene_log(
        game_state,
        [(npc_a, None, "hail", None), (npc_b, None, "hail", None)],
        dialogue_entries,
    )

    npc_entries = [entry for entry in game_state.scene_action_log if entry.actor_kind == ActorKind.NPC]
    assert [entry.actor_uuid for entry in npc_entries] == [npc_a.uuid, npc_b.uuid]
    assert all(entry.action_type == "TALK" for entry in npc_entries)
    assert npc_entries[0].description == "State your business."
    assert npc_entries[1].description == "Move along, stranger."
