"""Alias-list rendering for the Narrator's raw-material lines.

Both POIs and scene NPCs expose multiple acceptable surface forms
(``"primary (aka: alt1, alt2)"``) so the Narrator LLM can alternate
between synonyms instead of repeating one label. For NPCs the alias
list is also a *gate*: the unintroduced NPC's alias list collapses to
the short descriptor, so a proper name never reaches the prompt and
the Narrator can not leak a name the player has not yet learned.

Lives in its own module so :mod:`cast.narrator` stays inside the
WPS202 module-member budget.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

_AKA_SEPARATOR = ", "


def _join_extras(extras: list[str]) -> str:
    """Join the non-primary alias entries with the canonical separator."""
    return _AKA_SEPARATOR.join(extras)


def format_aka_label(aliases: list[str]) -> str:
    """Render a non-empty alias list as ``primary (aka: alt1, alt2)``.

    A single-alias list collapses to the bare primary so the Narrator
    sees no spurious ``(aka: …)`` suffix when there is nothing to
    alternate with.
    """
    primary = aliases[0]
    extras = aliases[1:]
    if not extras:
        return primary
    return "{0} (aka: {1})".format(primary, _join_extras(extras))


def format_poi_aliases(poi: Any) -> str:
    """Render a POI as ``primary (aka: alias1, alias2)``.

    POIs with a single name render just that name.
    """
    return format_aka_label(list(poi.names))


def format_scene_npc_label(snpc: Any, game_state: Any) -> str:
    """Render a ``SceneNPC`` label, gating proper names on ``known_npcs``.

    Introduced NPCs render as ``Name (Occupation) (aka: Name, the <occupation>)``
    so the Narrator can alternate between synonyms. NPCs the player
    has not been introduced to render as their ``short_descriptor`` if
    the card carries one, else the scene-side ``role`` tag. A ``uuid``
    set on the ``SceneNPC`` that is missing from ``game_state.npcs``
    is a broken invariant the NPC Ticker is supposed to prevent —
    surfaced as a warning so operators can trace the divergence while
    the player-facing fallback keeps rendering.
    """
    if snpc.uuid:
        npc = game_state.npcs.get(snpc.uuid)
        if npc is not None:
            return format_aka_label(npc.known_names_for_player(game_state, snpc.role))
        logger.warning(
            "narrator_aliases.format_scene_npc_label: scene uuid={0} role={1} missing from game_state.npcs",
            snpc.uuid,
            snpc.role,
        )
    return snpc.role


def resolve_dialogue_npc_label(npc_uuid: str, fallback_name: str, game_state: Any) -> str:
    """Render a dialogue/npc-turn speaker label, gated on ``known_npcs``.

    Mirrors :func:`format_poi_aliases` for NPCs. The full alias list
    from :meth:`NPCCard.known_names_for_player` is exposed so the
    Narrator can alternate between synonyms — and, for unintroduced
    NPCs, the list collapses to the short descriptor so a proper name
    never reaches the prompt.

    A scene-side ``SceneNPC.role`` is not available at this call site
    (dialogue/npc-turn entries do not carry the scene role), so the
    NPC's stored name is used as the role fallback. That fallback only
    surfaces when the card has neither ``short_descriptor`` nor a
    known introduction — a state ``NPCGenerator`` should not produce —
    and matches the behaviour the schema's ``npc_name`` field already
    carries for internal consumers.
    """
    if not npc_uuid:
        return fallback_name
    npc = game_state.npcs.get(npc_uuid)
    if npc is None:
        logger.warning(
            "narrator_aliases.resolve_dialogue_npc_label: uuid={0} missing from game_state.npcs",
            npc_uuid,
        )
        return fallback_name
    return format_aka_label(npc.known_names_for_player(game_state, fallback_name))
