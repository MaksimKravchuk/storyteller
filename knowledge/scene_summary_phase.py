"""Phase 1 of scene-end consolidation — the per-NPC summary memory.

Phase 1 is one LLM batch call per scene; :func:`run_summary_phase`
wraps it so a failure here does not abort the resilient
significant-event phase (after which the scene-swap caller wipes the
action log).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

from loguru import logger

from knowledge import salience as salience_presets
from models.scene_action_log import ActorKind, SceneActionEntry

if TYPE_CHECKING:
    from knowledge.memory import DialoguePair, MemoryManager
    from knowledge.scene_consolidation import SceneConsolidationRequest


async def run_summary_phase(manager: MemoryManager, request: SceneConsolidationRequest) -> None:
    """Run phase 1, swallowing its failure so phase 2 still persists.

    Phase 1 is a single LLM batch call; a timeout or rate-limit there
    must not abort consolidation, because the scene-swap caller wipes
    the action log immediately after this returns — a propagated
    phase-1 error would skip the resilient significant-event phase and
    permanently lose every combat / intimidation / witness node.
    ``CancelledError`` still propagates so cooperative cancellation is
    not silently turned into a log line.
    """
    try:
        await _summary_phase(manager, request)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception(
            "Scene per-NPC summary phase failed; significant events still persist (entries={}, npcs={}, location={})",
            len(request.entries),
            len(request.present_npc_uuids),
            request.location_id,
        )


async def _summary_phase(manager: MemoryManager, request: SceneConsolidationRequest) -> None:
    """Write one summary memory per present NPC.

    Each NPC's transcript is scoped to its **presence window**: entries
    from the start of the turn in which the NPC first appears (it acts,
    or is listed in an event's ``witness_ids``) through scene end. An
    NPC that never appears in the log gets no summary node — it was
    uninvolved. Anchoring on the turn rather than the exact entry keeps
    a replying NPC's memory of the player utterance it just answered
    (both share one ``game_clock`` — the clock advances once per turn).

    Tradeoff: an NPC present for entire *earlier* turns but with no
    signal in them starts remembering only from its first active turn.
    This narrow under-attribution is deliberate and preferred over the
    reverse — fabricating a first-person memory of events the NPC was
    not present for (e.g. an NPC who joined the scene at the end).
    """
    pairs: list[DialoguePair] = []
    for npc_uuid in request.present_npc_uuids:
        start = _presence_start_index(request.entries, npc_uuid)
        if start is None:
            continue
        rendered = _render_log_for_summariser(request.entries[start:], request.player_appearance)
        pairs.append((npc_uuid, rendered))
    if not pairs:
        return
    await manager.summarize_interactions_batch(
        pairs,
        game_time=request.game_time,
        location_id=request.location_id,
        salience=salience_presets.ROUTINE_DIALOGUE,
        subject_id=request.player_subject_id,
    )


def _first_appearance_index(entries: list[SceneActionEntry], npc_uuid: UUID) -> int | None:
    """Index of the first entry where *npc_uuid* acts or is a witness.

    ``witness_ids`` are stored as strings on the entry metadata
    (JSONB-safe), so the UUID is stringified before the membership test.
    Returns ``None`` when the NPC never appears.
    """
    witness_key = str(npc_uuid)
    return next(
        (
            idx
            for idx, entry in enumerate(entries)
            if entry.actor_uuid == npc_uuid or witness_key in entry.metadata.get("witness_ids", ())
        ),
        None,
    )


def _presence_start_index(entries: list[SceneActionEntry], npc_uuid: UUID) -> int | None:
    """Index of the first entry of the turn *npc_uuid* first appears in.

    The first-appearance index is walked back to the first entry
    sharing the matching entry's ``game_clock`` so the whole turn —
    including the player utterance the NPC reacted to — stays in the
    transcript. Returns ``None`` when the NPC never appears.
    """
    first_idx = _first_appearance_index(entries, npc_uuid)
    if first_idx is None:
        return None
    pivot_clock = entries[first_idx].game_clock
    start = first_idx
    while start > 0 and entries[start - 1].game_clock == pivot_clock:
        start -= 1
    return start


def _render_log_for_summariser(
    entries: list[SceneActionEntry],
    player_appearance: str | None = None,
) -> str:
    """Flatten the scene log into a transcript the summariser prompt can read.

    When ``player_appearance`` is supplied, player entries render
    through :func:`cast.player_context.render_player_entry` so the
    produced memory anchors on who the player visibly was.
    """
    from cast.player_context import render_player_entry

    lines: list[str] = []
    for entry in entries:
        if entry.actor_kind == ActorKind.PLAYER and player_appearance is not None:
            lines.append(render_player_entry(entry.action_type, entry.description, player_appearance))
        else:
            speaker = entry.actor_name or entry.action_type or "Event"
            lines.append("{speaker}: {desc}".format(speaker=speaker, desc=entry.description))
    return "\n".join(lines)
