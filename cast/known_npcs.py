"""Helpers to populate ``PlayerState.known_npcs`` procedurally.

Two signals feed the set:

* **Signal A** — the Actor's ``[REVEALED: ...]`` inline tag. Parsed
  tokens flow through :func:`apply_revealed_reply` and are resolved
  to NPC UUIDs.
* **Signal B** — the raw player input text. Any scene NPC whose name
  appears as a whole-word (case-insensitive) match is added via
  :func:`mark_player_text_introductions`, invoked once per
  non-clarification turn.

Scene isolation is the load-bearing invariant: same-name NPCs in
other scenes must never leak into ``known_npcs``.
"""

from __future__ import annotations

import re
from typing import Any, Iterable
from uuid import UUID

from cast.director_object_interaction import initialised_scene_witnesses
from models.game_state import GameState

_SELF_TOKEN = "self"


def _build_scene_name_index(game_state: GameState) -> dict[str, UUID]:
    """Map lowercase NPC name → UUID for every initialised scene NPC."""
    index: dict[str, UUID] = {}
    for npc_uuid in initialised_scene_witnesses(game_state):
        name = game_state.npcs[npc_uuid].name
        if name:
            index[name.lower()] = npc_uuid
    return index


def _resolve_single_token(
    raw_token: str,
    speaker_uuid: UUID,
    scene_uuids: set[UUID],
    name_index: dict[str, UUID],
) -> UUID | None:
    """Resolve one ``[REVEALED: ...]`` token to an NPC UUID, or ``None``."""
    token = raw_token.strip()
    if not token:
        return None
    if token.lower() == _SELF_TOKEN:
        return speaker_uuid if speaker_uuid in scene_uuids else None
    return name_index.get(token.lower())


def resolve_revealed_uuids(
    tokens: Iterable[str],
    speaker_uuid: UUID,
    game_state: GameState,
) -> set[UUID]:
    """Resolve ``[REVEALED: ...]`` tokens to NPC UUIDs for the current scene.

    ``"self"`` maps to ``speaker_uuid``. Any other token is matched
    case-insensitively against ``npc.name`` for NPCs in the current
    scene. Tokens that do not resolve are silently dropped — an LLM
    hallucination must not corrupt ``known_npcs`` with a UUID that has
    no corresponding NPC.
    """
    scene_uuids = set(initialised_scene_witnesses(game_state))
    name_index = _build_scene_name_index(game_state)
    resolved: set[UUID] = set()
    for raw_token in tokens:
        hit = _resolve_single_token(raw_token, speaker_uuid, scene_uuids, name_index)
        if hit is not None:
            resolved.add(hit)
    return resolved


def apply_revealed_reply(reply: Any, speaker_uuid: UUID, game_state: GameState) -> None:
    """Union resolved UUIDs from an Actor reply into ``known_npcs``.

    Most replies carry no revealed tokens; the early return keeps the
    common case branchless at call sites.
    """
    if not reply.revealed_names:
        return
    game_state.player.known_npcs.update(
        resolve_revealed_uuids(reply.revealed_names, speaker_uuid, game_state),
    )


def scan_player_text_for_known_uuids(
    player_text: str,
    game_state: GameState,
) -> set[UUID]:
    """Return UUIDs of scene NPCs whose name appears as a whole word in *player_text*.

    Match is case-insensitive and word-boundary-guarded so ``"Art"``
    inside ``"Arthur"`` does not false-match. Scoped to the current
    scene so typing a name never flags a same-named NPC elsewhere.
    """
    if not player_text:
        return set()
    return {
        npc_uuid
        for name, npc_uuid in _build_scene_name_index(game_state).items()
        if re.search(r"\b{0}\b".format(re.escape(name)), player_text, re.IGNORECASE)
    }


def mark_player_text_introductions(player_text: str, game_state: GameState) -> set[UUID]:
    """Apply Signal B to *game_state* and return the newly-added UUIDs.

    Whole-word matches of scene-NPC names are unioned into
    ``game_state.player.known_npcs``. The returned set is the subset
    that was *newly* added — useful for any future telemetry that
    wants to emit an introduction event.
    """
    matched = scan_player_text_for_known_uuids(player_text, game_state)
    known = game_state.player.known_npcs
    newly_known = matched - known
    known.update(matched)
    return newly_known
