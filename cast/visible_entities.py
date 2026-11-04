"""Collect the list of player-visible entities for a turn.

The collector is the single source of truth for "what can the player see
and interact with this turn?" — NPCs, points of interest, and tracked
items. It stitches together :meth:`NPCCard.known_names_for_player`
(knowledge gating) and the typed :class:`PointOfInterest` aliases into
the shared vocabulary that :func:`formatting.entity_markup.wrap_entities`
uses to wrap inline spans in narrator prose.
"""

from __future__ import annotations

from collections import Counter
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


def _make_npc_entity(snpc: Any, game_state: Any, all_npcs: dict, shared_roles: set[str]) -> VisibleEntity | None:
    """Return a ``VisibleEntity`` for ``snpc``, or ``None`` to skip it.

    Uninitialised stubs (no uuid) and stale uuids that no longer match a
    registered ``NPCCard`` both yield ``None``; the latter logs a warning
    that mirrors :func:`cast.narrator_aliases.format_scene_npc_label` so
    operators see the divergence from both render paths.
    """
    if snpc.uuid is None:
        return None
    card = all_npcs.get(snpc.uuid)
    if card is None:
        logger.warning(
            "visible_entities._npc_entities: scene uuid={0} role={1} missing from game_state.npcs",
            snpc.uuid,
            snpc.role,
        )
        return None
    names = card.known_names_for_player(game_state, snpc.role)
    # The scene role ("городовой у будки") is how the Narrator's scene prose
    # tends to refer to the NPC, so it is matched too. It only steers which
    # words become clickable; the gesture still resolves to the gated label.
    # A role two NPCs share would link both mentions to one of them, so it is skipped.
    if snpc.role and snpc.role not in shared_roles and snpc.role not in names:
        names = [*names, snpc.role]
    return VisibleEntity(kind="npc", id=str(snpc.uuid), names=names)


def _npc_entities(scene: Any, game_state: Any) -> list[VisibleEntity]:
    all_npcs = getattr(game_state, "npcs", {}) or {}
    role_counts = Counter(snpc.role for snpc in scene.npcs_present)
    shared_roles = {role for role in role_counts if role_counts[role] > 1}
    candidates = (_make_npc_entity(snpc, game_state, all_npcs, shared_roles) for snpc in scene.npcs_present)
    return [entity for entity in candidates if entity is not None]


def _poi_entities(scene: Any) -> list[VisibleEntity]:
    entities: list[VisibleEntity] = []
    for poi in scene.points_of_interest:
        poi_id = str(poi.uuid)
        poi_names = list(poi.names)
        entities.append(VisibleEntity(kind="poi", id=poi_id, names=poi_names))
    return entities


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
