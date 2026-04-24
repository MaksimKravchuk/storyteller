"""Opportunity-window detection for NPC autonomous turns.

When an NPC shares a scene with someone they have a standing hostile
goal toward — encoded either as a hostility-flavoured relationship label
or as a violence-flavoured knowledge fact mentioning that NPC by name —
the autonomous-turn prompt lifts the baseline "most turns are routine"
nudge and appends an OPPORTUNITY clause so the LLM can choose in
character whether to act on the moment.

Routine NPCs (empty / peaceful relationships, neutral knowledge) fall
through every gate here and see the unchanged baseline prompt.

Keywords match on **word boundaries**, not raw substrings — otherwise
``"kill"`` would fire on ``"skillful"`` and ``"harm"`` on
``"pharmacist"``, misrouting peaceful NPCs with perfectly benign labels.
"""

from __future__ import annotations

import re

from knowledge.query import KnowledgeQueryEngine
from models.game_state import GameState
from models.npc_card import NPCCard
from models.scene import Scene

RELATIONSHIP_HOSTILITY_KEYWORDS: frozenset[str] = frozenset(
    (
        "kill",
        "murder",
        "murderous",
        "harm",
        "wound",
        "enemy",
        "rival",
        "foe",
        "vendetta",
        "vengeance",
        "hostile",
    ),
)
KNOWLEDGE_VIOLENCE_KEYWORDS: frozenset[str] = frozenset(("kill", "murder", "harm", "wound"))

_OPPORTUNITY_TEMPLATE = (
    "OPPORTUNITY: {target} — the target of your standing hostile intent — "
    "is right here, right now. Every turn you wait is a turn you let this "
    "moment slip. Decide what THIS character, in THIS mood, with THIS "
    "equipment would do: ATTACK directly, approach under STEALTH first, "
    "or IDLE only if there is a concrete obstacle (witnesses, lack of "
    "weapon, personal code) that makes acting right now impossible. "
    "Name that obstacle in your action description if you choose to wait."
)

TACTICAL_HOSTILE_CLAUSE = (
    "TACTICAL CHOICE: You have a hostile goal. Pick your approach deliberately:\n"
    "  STEALTH — close in unseen; use this when your target is not watching you.\n"
    "  MOVE    — reposition to a better angle or closer range before committing.\n"
    "  ATTACK  — direct strike; use this only when you have a clear opening.\n"
    "Commit to one action. Do not hedge."
)


# Full-token boundary pattern: uses [^a-zA-Z] instead of \b so that
# "kill" fires on "murderous_enemy" (underscore-separated tokens) while
# still rejecting "skillful" and "pharmacist" (alphabetic neighbours).
_FULL_TOKEN_RE = r"(?:^|[^a-zA-Z])(?:{0})(?:[^a-zA-Z]|$)"

_RELATIONSHIP_KEYWORD_RE = re.compile(_FULL_TOKEN_RE.format("|".join(RELATIONSHIP_HOSTILITY_KEYWORDS)), re.IGNORECASE)
_KNOWLEDGE_KEYWORD_RE = re.compile(_FULL_TOKEN_RE.format("|".join(KNOWLEDGE_VIOLENCE_KEYWORDS)), re.IGNORECASE)


def get_opportunity_clause(npc: NPCCard, game_state: GameState) -> str | None:
    """Return a directive OPPORTUNITY clause naming the hostile target, or None.

    When a hostile co-located target is found — via relationship label or
    violent knowledge fact — the returned string names that target and
    instructs the Actor LLM to choose ATTACK, STEALTH, or IDLE with a
    named obstacle. Returns ``None`` when no gate fires (routine turn).
    """
    scene = game_state.current_scene
    if scene is None:
        return None
    co_located = _co_located_npc_uuids(scene, npc)
    if not co_located:
        return None
    target_name = _name_from_relationship(npc, co_located, game_state) or _name_from_knowledge(
        npc, co_located, game_state
    )
    if target_name is None:
        return None
    return _OPPORTUNITY_TEMPLATE.format(target=target_name)


def _co_located_npc_uuids(scene: Scene, self_npc: NPCCard) -> list[str]:
    uuids: list[str] = []
    for snpc in scene.npcs_present:
        if snpc.uuid and snpc.uuid != self_npc.uuid:
            uuids.append(snpc.uuid)
    return uuids


def _name_from_relationship(
    npc: NPCCard,
    co_located_uuids: list[str],
    game_state: GameState,
) -> str | None:
    co_located_set = set(co_located_uuids)
    for target_uuid, label in npc.relationships.items():
        name = _resolve_hostile_rel(target_uuid, label, co_located_set, game_state)
        if name is not None:
            return name
    return None


def _resolve_hostile_rel(
    target_uuid: str,
    label: str | None,
    co_located_set: set[str],
    game_state: GameState,
) -> str | None:
    if target_uuid not in co_located_set:
        return None
    if not _RELATIONSHIP_KEYWORD_RE.search(label or ""):
        return None
    target_npc = game_state.npcs.get(target_uuid)
    if target_npc is None:
        return None
    return target_npc.name


def _name_from_knowledge(
    npc: NPCCard,
    co_located_uuids: list[str],
    game_state: GameState,
) -> str | None:
    co_located_names = _co_located_display_names(co_located_uuids, game_state)
    if not co_located_names:
        return None
    query_engine = KnowledgeQueryEngine(game_state.knowledge_graph)
    knowledge_text = query_engine.get_context_for_npc(npc, topic_tags=None)
    if not knowledge_text or not _KNOWLEDGE_KEYWORD_RE.search(knowledge_text):
        return None
    return _names_in_text(co_located_names, knowledge_text)


def _names_in_text(names: list[str], text: str) -> str | None:
    """Return the first name from *names* that appears as a full token in *text*, or None."""
    for candidate in names:
        if not candidate:
            continue
        pattern = _FULL_TOKEN_RE.format(re.escape(candidate))
        if re.search(pattern, text, re.IGNORECASE):
            return candidate
    return None


def _co_located_display_names(co_located_uuids: list[str], game_state: GameState) -> list[str]:
    """Resolve UUIDs to NPC display names, skipping any not registered in game state."""
    names: list[str] = []
    for uuid in co_located_uuids:
        npc = game_state.npcs.get(uuid)
        if npc is not None:
            names.append(npc.name)
    return names
