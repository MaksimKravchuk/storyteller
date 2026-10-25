"""Seat a place's present residents into a freshly built scene."""

from __future__ import annotations

import re

from cast._place_residents import present_residents
from models.game_state import GameState
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC

_ROLE_WORD_MIN = 4
_WORD_RE = re.compile(r"\w+")


def seat_residents(game_state: GameState, scene: Scene) -> None:
    """Put the residents who are there now at the head of ``scene.npcs_present``."""
    seated = {snpc.uuid for snpc in scene.npcs_present if snpc.uuid}
    present = present_residents(game_state, scene.location_id)
    arriving = [npc for npc in present if npc.uuid not in seated]
    if not arriving:
        return
    newcomers = [snpc for snpc in scene.npcs_present if _is_newcomer(snpc, arriving)]
    scene.npcs_present = [_seat_for(npc) for npc in arriving] + newcomers


def _is_newcomer(snpc: SceneNPC, arriving: list[NPCCard]) -> bool:
    """Keep a Scene Builder role unless it re-describes an arriving resident.

    The Scene Builder often lists a resident again as a role ("net-mender
    woman"); generating a card for it would duplicate them.
    """
    return snpc.uuid is not None or not _describes_any(snpc.role, arriving)


def _seat_for(npc: NPCCard) -> SceneNPC:
    return SceneNPC(role=npc.occupation or npc.name, uuid=npc.uuid)


def _describes_any(role: str, npcs: list[NPCCard]) -> bool:
    """Return True when *role* names one of *npcs* or shares a word with their occupation."""
    role_text = role.lower()
    role_words = _significant_words(role_text)
    for npc in npcs:
        name = npc.name.lower()
        if name and name in role_text:
            return True
        if role_words & _significant_words(npc.occupation.lower()):
            return True
    return False


def _significant_words(text: str) -> set[str]:
    words = _WORD_RE.findall(text)
    return {word for word in words if len(word) >= _ROLE_WORD_MIN}
