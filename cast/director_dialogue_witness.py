"""Co-witness memory broadcast for dialogue turns (KER-11).

Emits a ``PERSONAL_EXPERIENCE`` memory for every non-targeted scene NPC
who was present when the player spoke to someone else. Lives outside
``director_dialogue`` so that module stays inside its WPS202 module-member
budget; lives outside ``director_dialogue_helpers`` so that module stays
pure (these helpers touch ``MemoryManager`` and are async).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from cast.dice import ContestRoll
from knowledge.memory import MemoryManager, record_player_learned_fact
from knowledge.node import KnowledgeScope
from models.game_state import GameState

WorkItem = tuple[Any, Any, str, ContestRoll | None]
DialogueEntry = dict[str, str]


def cowitness_uuids(
    targeted_uuids: set[UUID],
    game_state: GameState,
) -> list[UUID]:
    """Return UUIDs of initialised scene NPCs who aren't the dialogue targets.

    A scene NPC counts as a co-witness when its ``uuid`` is set *and*
    the matching ``NPCCard`` is already registered in ``game_state.npcs``
    — that is, :meth:`DialogueHandler.init_scene_npcs` has already run
    on it this turn (or a previous one). Uninitialised ``SceneNPC``
    stubs are skipped: they have no graph node yet, so attaching a
    ``WITNESSED`` edge would dangle.
    """
    scene = game_state.current_scene
    if not scene:
        return []
    return [
        snpc.uuid
        for snpc in scene.npcs_present
        if snpc.uuid is not None and snpc.uuid in game_state.npcs and snpc.uuid not in targeted_uuids
    ]


def _render_reply(entry: DialogueEntry) -> str:
    """Render a single dialogue entry as ``"<name> replied: <text>"``."""
    speaker = entry.get("npc_name", "")
    reply = entry.get("response", "")
    return "{0} replied: {1}".format(speaker, reply)


def format_overheard_text(
    player_action: str,
    work_items: list[WorkItem],
    dialogue_entries: list[DialogueEntry],
) -> str:
    """Render the raw transcript a co-witness would carry away from the scene.

    The text deliberately mentions every targeted NPC *by name* so a
    later ``get_memories_about`` query can match on the statement, the
    speaker, or the listener. Co-witness memories bypass the LLM
    summariser entirely — the raw exchange is cheap, deterministic,
    and already contains enough signal for downstream Actor prompts.
    """
    targeted_names = ", ".join(wi[0].name for wi in work_items) or "someone"
    responses = " ".join(_render_reply(entry) for entry in dialogue_entries)
    return '[overheard] You overheard the player tell {0}: "{1}". {2}'.format(
        targeted_names,
        player_action,
        responses,
    ).strip()


async def broadcast_cowitness_memories(
    work_items: list[WorkItem],
    dialogue_entries: list[DialogueEntry],
    player_action: str,
    game_state: GameState,
    memory_manager: MemoryManager,
) -> None:
    """Emit a personal-experience memory for every non-targeted scene NPC.

    Co-witness memories are created via
    :meth:`MemoryManager.create_memory_from_event` with
    ``KnowledgeScope.LOCAL`` so they land as ``PERSONAL_EXPERIENCE``
    nodes — exactly the source class
    :meth:`KnowledgeQueryEngine.get_memories_about` returns. No LLM
    calls are issued; the overheard transcript is embedded verbatim so
    a subsequent Actor prompt asking NPC B about the player's
    statement has something concrete to match against.

    When no dialogue was actually produced this turn (``work_items``
    empty — e.g. a TALK plan that resolved to a pure "look around"
    with no targets), we short-circuit: there is nothing for the
    bystanders to overhear and no transcript to store.
    """
    if not work_items or not dialogue_entries:
        return
    targeted_uuids = {wi[0].uuid for wi in work_items}
    witnesses = cowitness_uuids(targeted_uuids, game_state)
    if not witnesses:
        return
    scene = game_state.current_scene
    overheard_text = format_overheard_text(player_action, work_items, dialogue_entries)
    created_ids = await memory_manager.create_memory_from_event(
        event_description=overheard_text,
        witness_ids=witnesses,
        scope=KnowledgeScope.LOCAL,
        location_id=scene.location_id if scene else None,
        game_time=game_state.game_clock,
    )
    record_player_learned_fact(game_state.player, created_ids)
