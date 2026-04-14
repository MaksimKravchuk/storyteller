"""City-scope helpers shared by :mod:`knowledge.rumor`.

Walks the location hierarchy to answer "which locations are in the
same city as this one?" so rumour propagation can restrict itself to
city-local listeners without leaking a rumour into other cities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.game_state import GameState
    from models.location import Location


_CITY_LOCATION_TYPE = "city"


def witnesses_at(game_state: GameState, location_id: str) -> list[str]:
    """Return NPC UUIDs currently present at ``location_id``."""
    location = game_state.locations.get(location_id)
    if location is None:
        return []
    return list(location.npcs_present)


def non_witness_city_npcs(
    game_state: GameState,
    event_location_id: str,
    witness_ids: list[str],
) -> list[tuple[str, str]]:
    """Return ``(npc_id, location_id)`` pairs for same-city non-witnesses.

    NPCs at the event's own location are treated as witnesses (whether
    or not they are listed in ``witness_ids``) and always excluded —
    they see the event first-hand in the scene.
    """
    ctx = _ListenerContext(
        city_ids=_same_city_locations(game_state.locations, event_location_id),
        witness_set=set(witness_ids),
        event_location_id=event_location_id,
    )
    return [
        (npc_id, location_id)
        for npc_id, npc in game_state.npcs.items()
        for location_id in (npc.location_id,)
        if location_id is not None and ctx.accepts(npc_id, location_id)
    ]


@dataclass(frozen=True)
class _ListenerContext:
    """Bundles the shared filter inputs for ``accepts()``."""

    city_ids: set[str]
    witness_set: set[str]
    event_location_id: str

    def accepts(self, npc_id: str, npc_location: str) -> bool:
        if npc_id in self.witness_set:
            return False
        if npc_location == self.event_location_id:
            return False
        return npc_location in self.city_ids


def _same_city_locations(
    locations: dict[str, Location],
    event_location_id: str,
) -> set[str]:
    """Return every location_id that shares a city with ``event_location_id``."""
    return _reachable_descendants(locations, _city_root(locations, event_location_id))


def _city_root(locations: dict[str, Location], location_id: str) -> str:
    """Walk up ``parent_location_id`` to the first city, or the topmost node."""
    current = location_id
    visited: set[str] = set()
    while current in locations and current not in visited:
        visited.add(current)
        node = locations[current]
        if node.location_type == _CITY_LOCATION_TYPE or node.parent_location_id is None:
            return current
        current = node.parent_location_id
    return location_id


def _reachable_descendants(locations: dict[str, Location], root_id: str) -> set[str]:
    """Return ``{root_id}`` plus every location whose parent chain reaches root."""
    reachable = {root_id}
    changed = True
    while changed:
        changed = False
        for loc_id, loc in locations.items():
            if loc_id not in reachable and loc.parent_location_id in reachable:
                reachable.add(loc_id)
                changed = True
    return reachable
