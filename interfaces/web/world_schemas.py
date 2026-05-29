"""Pydantic models for the dashboard ``WorldView`` payload.

Sibling of :mod:`interfaces.web.character_schemas`. Where ``CharacterInfo``
projects the player's own state (inventory, known NPCs, learned facts), this
module projects the *world around* the player — a connected-locations map, the
people present in the current scene, and the game clock — for the Map and
People & Time dashboard panels. Inventory and Knowledge continue to ride on
``CharacterInfo``; only Map / People / Clock are new data, so they live here.
"""

from __future__ import annotations

from pydantic import BaseModel


class LocationNode(BaseModel):
    """A single place rendered as a node on the map.

    ``id`` is ``str(uuid)`` — an opaque token the client never parses;
    ``location_type`` is already normalised to a fixed slug set by the
    ``Location`` model, so the client can style it without a wire-projection map.
    """

    id: str
    name: str
    location_type: str


class MapView(BaseModel):
    """The player's "mental map": where they are and where they can go.

    ``current`` is ``None`` when the player has no resolved location yet.
    ``connections`` are the directly reachable/known neighbours (sorted by
    name). ``breadcrumb`` is the ancestor chain (outermost first, e.g.
    Rome → Forum), excluding ``current`` itself.
    """

    current: LocationNode | None
    connections: list[LocationNode]
    breadcrumb: list[LocationNode]


class ScenePerson(BaseModel):
    """An NPC present in the current scene.

    ``label`` is already name-gated by ``NPCCard.label_for_player`` (the NPC's
    name once introduced, otherwise a descriptor or the scene role). ``known``
    tells the client whether the player has been introduced, so strangers can
    be styled differently.
    """

    label: str
    role: str
    known: bool


class WorldClock(BaseModel):
    """The current game time, derived from the continuous ``game_clock``."""

    day: int
    time_of_day: str
    hour: int


class WorldView(BaseModel):
    """The dashboard payload for the Map and People & Time panels."""

    map: MapView
    people: list[ScenePerson]
    clock: WorldClock
