"""Knowledge-graph persistence of autonomous NPC combat events.

Wraps :meth:`~knowledge.memory.MemoryManager.create_memory_from_event`
with the witness list and event-text shape the rubric/detectors expect:
both combatants' names, an attack verb, and the resolution clause
(lethality + new state) in a single LOCAL-scope node, with co-located
NPCs added as witnesses.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID

from cast._npc_outcome import OutcomeKind
from knowledge.memory import MemoryManager
from knowledge.node import KnowledgeScope
from models.game_state import GameState
from models.npc_card import NPCCard

_RESOLUTION_CLAUSE: MappingProxyType[tuple[OutcomeKind, str], str] = MappingProxyType(
    {
        (OutcomeKind.PHYSICAL, "dead"): "attacked and killed {target} with a lethal blow",
        (OutcomeKind.PHYSICAL, "wounded"): "attacked and wounded {target} in a non-lethal hit",
        (OutcomeKind.MOOD, "frightened"): "intimidated {target} into submission",
    },
)


@dataclass(frozen=True)
class CombatEvent:
    """Inputs for :func:`persist_combat_memory`.

    Bundling keeps the signature within the WPS function-argument
    budget. ``location_id=None`` falls back to the current scene's
    location; off-scene callers (the background ticker) pass the
    actor's own location id. ``kind`` and ``new_value`` together pick
    the resolution clause in the persisted event text — physical+dead
    reads as a lethal kill, physical+wounded as a non-lethal hit, and
    mood+frightened as a successful intimidation.
    """

    actor: NPCCard
    target: NPCCard
    new_value: str
    kind: OutcomeKind
    location_id: UUID | None = None


def _co_located_witness_ids(
    actor: NPCCard,
    target: NPCCard,
    game_state: GameState,
    location_id: UUID | None,
) -> list[UUID]:
    """Return UUIDs of every NPC who would have witnessed the clash.

    Includes both combatants plus every NPC currently at ``location_id``.
    Falls back to the current scene when ``location_id`` is the scene's
    location, so the in-scene case still walks ``scene.npcs_present``.
    """
    witnesses: set[UUID] = set()
    witnesses.add(actor.uuid)
    witnesses.add(target.uuid)
    if location_id is None:
        return list(witnesses)
    location = game_state.locations.get(location_id)
    if location is not None:
        witnesses.update(location.npcs_present)
    return list(witnesses)


def _format_combat_event(event: CombatEvent) -> str:
    """Render the LOCAL memory text describing the clash *and its resolution*.

    The clause carries who won, the severity (lethal vs non-lethal for
    physical, intimidation submission for mood), and the new state — so
    co-located witnesses can later recall how the fight ended, not just
    that one started. The trailing ``; X is now Y.`` keeps the new
    state explicit alongside the narrative phrasing.
    """
    clause_template = _RESOLUTION_CLAUSE[(event.kind, event.new_value)]
    clause = clause_template.format(target=event.target.name)
    return "{0} {1}; {2} is now {3}.".format(event.actor.name, clause, event.target.name, event.new_value)


async def persist_combat_memory(
    memory_manager: MemoryManager,
    event: CombatEvent,
    game_state: GameState,
) -> None:
    """Write a LOCAL knowledge-graph node so witnesses recall the clash."""
    location_id = event.location_id
    if location_id is None:
        scene = game_state.current_scene
        location_id = scene.location_id if scene else None
    await memory_manager.create_memory_from_event(
        event_description=_format_combat_event(event),
        witness_ids=_co_located_witness_ids(event.actor, event.target, game_state, location_id),
        scope=KnowledgeScope.LOCAL,
        location_id=location_id,
        game_time=game_state.game_clock,
    )
