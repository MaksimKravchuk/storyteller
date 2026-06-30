"""Scheduled-event adapter for off-screen social memory effects."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from uuid import UUID

from cast._npc_social_memory import SocialMemoryEvent, persist_social_memory_and_goal
from knowledge.memory import MemoryEvent, MemoryManager
from models.game_state import GameState
from timeline._uuid_coerce import coerce_uuid
from timeline.event import EventEffect, GameEvent

_SOCIAL_MEMORY_EFFECT = "SOCIAL_MEMORY"
MemoryEventBuilder = Callable[[GameEvent], MemoryEvent]


def _resolve_social_effect(
    effect: EventEffect, location_id: UUID | None, game_state: GameState
) -> SocialMemoryEvent | None:
    actor_id = coerce_uuid(effect.effect_data.get("actor_id"))
    target_id = coerce_uuid(effect.effect_data.get("target_id", effect.target_id))
    if actor_id is None or target_id is None:
        return None
    actor = game_state.npcs.get(actor_id)
    target = game_state.npcs.get(target_id)
    if actor is None or target is None:
        return None
    return SocialMemoryEvent(
        actor=actor,
        target=target,
        kind=str(effect.effect_data.get("kind", "")),
        location_id=location_id,
    )


async def _process_social_effect(
    effect: EventEffect,
    location_id: UUID | None,
    game_state: GameState,
    memory_manager: MemoryManager,
) -> None:
    if effect.effect_type.upper() != _SOCIAL_MEMORY_EFFECT:
        return
    social_event = _resolve_social_effect(effect, location_id, game_state)
    if social_event is None:
        return
    await persist_social_memory_and_goal(memory_manager, social_event, game_state)


def _social_effect_writes(
    events: list[GameEvent], game_state: GameState, memory_manager: MemoryManager
) -> Iterator[Awaitable[None]]:
    return (
        _process_social_effect(effect, ev.location_id, game_state, memory_manager)
        for ev in events
        for effect in ev.effects
    )


async def process_social_effects(
    events: list[GameEvent],
    game_state: GameState,
    memory_manager: MemoryManager,
) -> None:
    """Persist social memory effects carried by completed remote events."""
    await _process_social_writes(tuple(_social_effect_writes(events, game_state, memory_manager)))


async def _process_social_writes(writes: tuple[Awaitable[None], ...]) -> None:
    if not writes:
        return
    await writes[0]
    await _process_social_writes(writes[1:])


def _remote_memory_writes(
    events: list[GameEvent],
    memory_manager: MemoryManager,
    build_memory_event: MemoryEventBuilder,
) -> Iterator[Awaitable[object]]:
    return (memory_manager.create_memory_from_event(build_memory_event(ev)) for ev in events)


async def process_remote_event_memories(
    events: list[GameEvent],
    game_state: GameState,
    memory_manager: MemoryManager,
    build_memory_event: MemoryEventBuilder,
) -> None:
    """Persist ordinary remote memories and social follow-on effects."""
    await asyncio.gather(*_remote_memory_writes(events, memory_manager, build_memory_event))
    await process_social_effects(events, game_state, memory_manager)
