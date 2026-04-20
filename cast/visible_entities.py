"""Collect the list of player-visible entities for a turn.

The collector is the single source of truth for "what can the player see
and interact with this turn?" — NPCs, points of interest, and tracked
items. It stitches together :meth:`NPCCard.known_names_for_player`
(knowledge gating) and the typed :class:`PointOfInterest` aliases so the
frontend chip row and the inline entity-markup post-match share one
vocabulary.
"""

from __future__ import annotations

from typing import Any

from models.visible_entity import VisibleEntity


def collect_visible_entities(scene: Any, game_state: Any, location: Any) -> list[VisibleEntity]:
    """Return every entity addressable by the player for the given scene.

    ``scene`` may be ``None`` on continuation turns with no rebuild — the
    caller should pass the active scene regardless so chips stay steady
    across turns. ``location`` is optional; when present its
    ``object_states`` keys surface as ``kind="item"`` entities for any
    tracked object not already represented by a POI name.
    """
    entities: list[VisibleEntity] = []
    if scene is not None:
        entities.extend(_npc_entities(scene, game_state))
        entities.extend(_poi_entities(scene))
    if location is not None:
        entities.extend(_item_entities(location, entities))
    return entities


def collect_for_turn(raw_outputs: Any, game_state: Any) -> list[VisibleEntity]:
    """Resolve the active scene + location and delegate to the collector.

    Uses ``raw_outputs.scene`` when present (new-scene turns) and falls
    back to ``game_state.current_scene`` so continuation turns still
    carry a chip row. The location is resolved through the player's
    ``location_id`` — consistent with the Narrator's resolution path.
    """
    active_scene = raw_outputs.scene or getattr(game_state, "current_scene", None)
    location = None
    if active_scene is not None:
        location = getattr(game_state, "locations", {}).get(active_scene.location_id)
    return collect_visible_entities(active_scene, game_state, location)


def _make_poi_entity(poi: Any) -> VisibleEntity:
    return VisibleEntity(kind="poi", id=poi.uuid, names=list(poi.names))


def _npc_entities(scene: Any, game_state: Any) -> list[VisibleEntity]:
    """Collect NPC entities from the scene, gated on player knowledge."""
    npc_entities: list[VisibleEntity] = []
    all_npcs = getattr(game_state, "npcs", {}) or {}
    for snpc in scene.npcs_present:
        if not snpc.uuid:
            continue
        card = all_npcs.get(snpc.uuid)
        if card is None:
            continue
        names = card.known_names_for_player(game_state, snpc.role)
        npc_entities.append(VisibleEntity(kind="npc", id=snpc.uuid, names=names))
    return npc_entities


def _poi_entities(scene: Any) -> list[VisibleEntity]:
    """Collect POI entities directly from typed ``scene.points_of_interest``."""
    return [_make_poi_entity(poi) for poi in scene.points_of_interest]


def _item_entities(location: Any, already_collected: list[VisibleEntity]) -> list[VisibleEntity]:
    """Surface ``location.object_states`` keys not already covered by a POI alias.

    The object-state key is reused as the entity id so chips for the
    same tracked object stay stable across turns.
    """
    object_states = getattr(location, "object_states", None) or {}
    if not object_states:
        return []
    covered = {name.lower() for entity in already_collected for name in entity.names}
    surfaced: list[VisibleEntity] = []
    for key in object_states:
        if any(key.lower() in name for name in covered):
            continue
        surfaced.append(VisibleEntity(kind="item", id=key, names=[key]))
    return surfaced
