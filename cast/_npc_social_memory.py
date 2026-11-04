"""Knowledge-graph persistence and goal seeding for off-screen social events."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID

from cast._npc_social_consequence import EVENT_HARM, EVENT_KINDNESS, apply_social_consequence
from knowledge import charge as charge_presets, salience as salience_presets
from knowledge.memory import MemoryEvent, MemoryManager
from knowledge.memory_slots import MemorySlots
from knowledge.node import KnowledgeScope
from models.game_state import GameState
from models.npc_card import NPCCard

_ACTION_BY_KIND: MappingProxyType[str, str] = MappingProxyType(
    {
        EVENT_HARM: "harmed",
        EVENT_KINDNESS: "helped",
    },
)
_OUTCOME_BY_KIND: MappingProxyType[str, str] = MappingProxyType(
    {
        EVENT_HARM: "grudge",
        EVENT_KINDNESS: "debt",
    },
)
_SALIENCE_BY_KIND: MappingProxyType[str, float] = MappingProxyType(
    {
        EVENT_HARM: salience_presets.RETALIATION,
        EVENT_KINDNESS: salience_presets.REMOTE_EVENT,
    },
)
_CHARGE_BY_KIND: MappingProxyType[str, charge_presets.ChargePreset] = MappingProxyType(
    {
        EVENT_HARM: charge_presets.RETALIATION,
        EVENT_KINDNESS: charge_presets.ROUTINE_DIALOGUE,
    },
)


@dataclass(frozen=True)
class SocialMemoryEvent:
    """A non-combat social consequence that happened away from the player."""

    actor: NPCCard
    target: NPCCard
    kind: str
    location_id: UUID | None = None
    source_event_id: UUID | None = None


def _location_id_for(event: SocialMemoryEvent, game_state: GameState) -> UUID | None:
    if event.location_id is not None:
        return event.location_id
    if event.target.location_id is not None:
        return event.target.location_id
    scene = game_state.current_scene
    return scene.location_id if scene else None


def _co_located_witness_ids(event: SocialMemoryEvent, game_state: GameState, location_id: UUID | None) -> list[UUID]:
    witnesses = {event.actor.uuid, event.target.uuid}
    if location_id is None:
        return list(witnesses)
    location = game_state.locations.get(location_id)
    if location is not None:
        witnesses.update(location.npcs_present)
    return list(witnesses)


def _format_event(event: SocialMemoryEvent) -> str:
    outcome = _OUTCOME_BY_KIND[event.kind]
    action = _ACTION_BY_KIND[event.kind]
    return "{0} formed a {1} after {2} {3} them off-screen.".format(
        event.target.name,
        outcome,
        event.actor.name,
        action,
    )


def _tags_for(event: SocialMemoryEvent) -> list[str]:
    """Return durable identifiers for downstream social-memory queries."""
    actor_id = event.actor.uuid
    target_id = event.target.uuid
    outcome = _OUTCOME_BY_KIND[event.kind]
    tags = [
        "social_memory",
        f"social_memory:{event.kind}",
        f"social_memory:{outcome}",
        f"actor:{actor_id}",
        f"target:{target_id}",
    ]
    if event.source_event_id is not None:
        source_event_id = event.source_event_id
        tags.append(f"source_event:{source_event_id}")
    return tags


async def persist_social_memory_and_goal(
    memory_manager: MemoryManager,
    event: SocialMemoryEvent,
    game_state: GameState,
) -> None:
    """Write a social memory node and seed a deterministic follow-on goal.

    Unknown social event kinds and missing goal kinds are skipped rather
    than raising: scheduled-event payloads are LLM-produced, while the
    follow-on goal enum is code-owned and may not support every desired
    social stance in older saves.
    """
    if event.kind not in _OUTCOME_BY_KIND:
        return
    location_id = _location_id_for(event, game_state)
    charge = _CHARGE_BY_KIND[event.kind]
    await memory_manager.create_memory_from_event(
        MemoryEvent(
            event_description=_format_event(event),
            witness_ids=_co_located_witness_ids(event, game_state, location_id),
            scope=KnowledgeScope.LOCAL,
            location_id=location_id,
            game_time=game_state.game_clock,
            salience=_SALIENCE_BY_KIND[event.kind],
            valence=charge.base_valence,
            charge_intensity=charge.base_intensity,
            charge_category=charge.category,
            subject_id=event.actor.uuid,
            tags=_tags_for(event),
            slots=MemorySlots(
                subject=event.actor.name,
                object=event.target.name,
                action=_ACTION_BY_KIND[event.kind],
                outcome=_OUTCOME_BY_KIND[event.kind],
            ),
        ),
    )
    apply_social_consequence(event.actor, event.target, event.kind, game_state.turn_count)
