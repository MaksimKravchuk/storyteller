"""Helpers to populate ``PlayerState.known_npcs`` procedurally (KER-29).

Two signals feed this set:

* **Signal A** — the Actor's ``[REVEALED: ...]`` inline tag (parsed in
  :mod:`cast.actor`). The dialogue pipeline calls
  :func:`resolve_revealed_uuids` to turn tokens into NPC UUIDs, scoped
  to the current scene so cross-scene same-name NPCs never leak.
* **Signal B** — the raw player input text. The Director pipeline
  calls :func:`scan_player_text_for_known_uuids` after action
  classification: any NPC in the current scene whose name appears as a
  whole-word (case-insensitive) match is considered already known.
"""

from __future__ import annotations

import re
from typing import Iterable

from models.game_state import GameState

_SELF_TOKEN = "self"


def _initialised_scene_npc_uuids(game_state: GameState) -> set[str]:
    """Return the UUIDs of NPCs present in the current scene that are registered.

    An uninitialised ``SceneNPC`` (only a role string, no UUID) cannot
    be recorded as known — there is no stable handle to store. Mirrors
    the scene-isolation filter used elsewhere in the Director.
    """
    scene = game_state.current_scene
    if scene is None:
        return set()
    npcs = game_state.npcs
    return {snpc.uuid for snpc in scene.npcs_present if snpc.uuid and snpc.uuid in npcs}


def _build_scene_name_index(game_state: GameState) -> dict[str, str]:
    """Map lowercase NPC name → UUID for every initialised scene NPC."""
    scene_uuids = _initialised_scene_npc_uuids(game_state)
    index: dict[str, str] = {}
    for npc_uuid in scene_uuids:
        name = game_state.npcs[npc_uuid].name
        if name:
            index[name.lower()] = npc_uuid
    return index


def _resolve_single_token(
    raw_token: str,
    speaker_uuid: str,
    scene_uuids: set[str],
    name_index: dict[str, str],
) -> str | None:
    """Resolve one ``[REVEALED: ...]`` token to an NPC UUID, or ``None``."""
    token = raw_token.strip()
    if not token:
        return None
    if token.lower() == _SELF_TOKEN:
        return speaker_uuid if speaker_uuid in scene_uuids else None
    return name_index.get(token.lower())


def resolve_revealed_uuids(
    tokens: Iterable[str],
    speaker_uuid: str,
    game_state: GameState,
) -> set[str]:
    """Resolve ``[REVEALED: ...]`` tokens to NPC UUIDs for the current scene.

    ``"self"`` maps to ``speaker_uuid``. Any other token is matched
    case-insensitively against ``npc.name`` for NPCs present in the
    current scene. Tokens that do not resolve are silently dropped —
    an LLM hallucination should not corrupt ``known_npcs`` with a
    UUID that has no corresponding NPC.
    """
    scene_uuids = _initialised_scene_npc_uuids(game_state)
    name_index = _build_scene_name_index(game_state)
    resolved: set[str] = set()
    for raw_token in tokens:
        hit = _resolve_single_token(raw_token, speaker_uuid, scene_uuids, name_index)
        if hit is not None:
            resolved.add(hit)
    return resolved


def scan_player_text_for_known_uuids(
    player_text: str,
    game_state: GameState,
) -> set[str]:
    """Return UUIDs of scene NPCs whose name appears as a whole word in *player_text*.

    Match is case-insensitive and word-boundary-guarded so ``"Art"``
    inside ``"Arthur"`` does not false-match. The scan is scoped to
    NPCs in the current scene — a player typing ``"Marcus"`` while
    standing somewhere else must not flag a distant Marcus as known.
    """
    if not player_text:
        return set()
    return {
        npc_uuid
        for name, npc_uuid in _build_scene_name_index(game_state).items()
        if re.search(r"\b{0}\b".format(re.escape(name)), player_text, re.IGNORECASE)
    }


def mark_player_text_introductions(player_text: str, game_state: GameState) -> set[str]:
    """Apply Signal B to the current game state and return the newly-added UUIDs.

    Whole-word matches of scene-NPC names are unioned into
    ``game_state.player.known_npcs``. The returned set is the subset
    that was *newly* added (useful for tests and any future telemetry
    that wants to emit an introduction event).
    """
    matched = scan_player_text_for_known_uuids(player_text, game_state)
    known = game_state.player.known_npcs
    newly_known = matched - known
    known.update(matched)
    return newly_known
