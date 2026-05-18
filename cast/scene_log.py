"""Append helpers for :class:`models.scene_action_log.SceneActionEntry`.

Every site that produces a player action, an NPC action/dialogue, or
an ambient witnessed event calls one of the ``append_*`` helpers here.
Significance classification lives in :mod:`cast.scene_log_classify`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from cast.scene_log_classify import classify_significance
from models.game_state import GameState
from models.scene_action_log import ActorKind, SceneActionEntry


@dataclass(frozen=True)
class WitnessedEvent:
    """Bundle of inputs for :func:`append_event`.

    Keeps the helper signature inside the WPS argument-count budget
    while still carrying the witness list and ``already_persisted``
    de-dup flag the consolidator needs.
    """

    event_type: str
    description: str
    witness_ids: list[UUID] = field(default_factory=list)
    target_uuid: UUID | None = None
    already_persisted: bool = False


def append_player_action(
    game_state: GameState,
    action_type: str,
    description: str,
    is_aggressive: bool = False,
) -> None:
    """Record a player action at the head of this turn's resolution."""
    metadata: dict[str, Any] = {}
    if is_aggressive:
        metadata["player_is_aggressive"] = True
    resolved_action_type = action_type or "PLAYER_INPUT"
    entry = SceneActionEntry(
        actor_kind=ActorKind.PLAYER,
        actor_uuid=game_state.player.uuid,
        actor_name=game_state.player.name,
        action_type=resolved_action_type,
        description=description,
        game_clock=game_state.game_clock,
        significant=classify_significance(ActorKind.PLAYER, resolved_action_type, metadata),
        metadata=metadata,
    )
    game_state.scene_action_log.append(entry)


def append_npc_action(
    game_state: GameState,
    npc: Any,
    action: Any,
) -> None:
    """Record one NPC's autonomous turn outcome."""
    metadata: dict[str, Any] = {}
    if action.contest_roll is not None:
        metadata["contest_outcome"] = action.contest_roll.outcome.value
    target_name = action.target if isinstance(action.target, str) else None
    entry = SceneActionEntry(
        actor_kind=ActorKind.NPC,
        actor_uuid=npc.uuid,
        actor_name=npc.name,
        action_type=action.action_type,
        description=action.action_description,
        target_name=target_name,
        game_clock=game_state.game_clock,
        significant=classify_significance(ActorKind.NPC, action.action_type, metadata),
        metadata=metadata,
    )
    game_state.scene_action_log.append(entry)


def append_npc_dialogue(
    game_state: GameState,
    npc: Any,
    response: str,
) -> None:
    """Record an NPC's reply on the player's TALK turn."""
    entry = SceneActionEntry(
        actor_kind=ActorKind.NPC,
        actor_uuid=npc.uuid,
        actor_name=npc.name,
        action_type="TALK",
        description=response,
        target_name=game_state.player.name,
        game_clock=game_state.game_clock,
        significant=False,
        metadata={},
    )
    game_state.scene_action_log.append(entry)


def append_event(
    game_state: GameState,
    event: WitnessedEvent,
) -> None:
    """Record an ambient witnessed event (combat, vandalism, etc.).

    ``event.already_persisted=True`` flags entries whose author already
    wrote a long-term node via
    :meth:`MemoryManager.create_memory_from_event` so the scene-end
    consolidator can skip them.
    """
    metadata = _event_metadata(event)
    entry = SceneActionEntry(
        actor_kind=ActorKind.EVENT,
        actor_uuid=None,
        actor_name="",
        action_type=event.event_type,
        description=event.description,
        target_uuid=event.target_uuid,
        game_clock=game_state.game_clock,
        significant=classify_significance(ActorKind.EVENT, event.event_type, metadata),
        metadata=metadata,
    )
    game_state.scene_action_log.append(entry)


def _event_metadata(event: WitnessedEvent) -> dict[str, Any]:
    """Build the JSON-safe metadata blob attached to a witnessed-event entry."""
    metadata: dict[str, Any] = {}
    if event.already_persisted:
        metadata["already_persisted"] = True
    if event.witness_ids:
        metadata["witness_ids"] = [str(wid) for wid in event.witness_ids]
    return metadata
