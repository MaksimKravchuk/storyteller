"""Collect the list of player-visible entities for a turn.

The collector is the single source of truth for "what can the player see
and interact with this turn?" — NPCs, points of interest, and tracked
items. It stitches together :meth:`NPCCard.known_names_for_player`
(knowledge gating) and the typed :class:`PointOfInterest` aliases into
the shared vocabulary that :func:`formatting.entity_markup.wrap_entities`
uses to wrap inline spans in narrator prose.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from models.visible_entity import VisibleEntity


def collect_visible_entities(scene: Any, game_state: Any, location: Any) -> list[VisibleEntity]:
    """Return every entity addressable by the player for the given scene.

    ``scene`` may be ``None`` on continuation turns with no rebuild.
    ``location`` is optional; when present its ``object_states`` keys
    surface as ``kind="item"`` entities for tracked objects not already
    represented by a POI alias.
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
    carry entity highlights. The location is looked up by the scene's
    ``location_id`` from ``game_state.locations``.
    """
    active_scene = raw_outputs.scene or getattr(game_state, "current_scene", None)
    location = None
    if active_scene is not None:
        location = getattr(game_state, "locations", {}).get(active_scene.location_id)
    return collect_visible_entities(active_scene, game_state, location)


def _make_poi_entity(poi: Any) -> VisibleEntity:
    return VisibleEntity(kind="poi", id=poi.uuid, names=list(poi.names))


def _npc_entities(scene: Any, game_state: Any) -> list[VisibleEntity]:
    npc_entities: list[VisibleEntity] = []
    all_npcs = getattr(game_state, "npcs", {}) or {}
    for snpc in scene.npcs_present:
        if not snpc.uuid:
            continue
        card = all_npcs.get(snpc.uuid)
        if card is None:
            # Invariant break: uuid assigned but no NPCCard registered. Mirrors
            # the warning in cast.narrator._format_npc_label so operators see
            # the same divergence from both render paths.
            logger.warning(
                "visible_entities._npc_entities: scene uuid={0} role={1} missing from game_state.npcs",
                snpc.uuid,
                snpc.role,
            )
            continue
        names = card.known_names_for_player(game_state, snpc.role)
        npc_entities.append(VisibleEntity(kind="npc", id=snpc.uuid, names=names))
    return npc_entities


def _poi_entities(scene: Any) -> list[VisibleEntity]:
    return [_make_poi_entity(poi) for poi in scene.points_of_interest]


def _item_entities(location: Any, already_collected: list[VisibleEntity]) -> list[VisibleEntity]:
    """Surface ``location.object_states`` keys not already covered by a POI alias.

    Suppression is token-boundary, not substring — a short key like
    ``"ar"`` must still surface even when a longer POI alias like
    ``"bar"`` happens to contain those characters. The object-state key
    doubles as the entity id so the same tracked object stays stable
    across turns.
    """
    object_states = getattr(location, "object_states", None) or {}
    if not object_states:
        return []
    covered_tokens: set[str] = set()
    for entity in already_collected:
        for name in entity.names:
            covered_tokens.update(name.lower().split())
    return [
        VisibleEntity(kind="item", id=key, names=[key])
        for key in object_states
        if not _key_covered_by_tokens(key, covered_tokens)
    ]


def _key_covered_by_tokens(key: str, covered_tokens: set[str]) -> bool:
    key_tokens = key.lower().split()
    if not key_tokens:
        return False
    return all(token in covered_tokens for token in key_tokens)
