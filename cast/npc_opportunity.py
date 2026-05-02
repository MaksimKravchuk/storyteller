"""Opportunity-window detection for NPC autonomous turns.

When an NPC shares a scene with someone they have a standing hostile
goal toward — encoded either as a hostile :class:`~models.relationship.Relationship`
or as a violence-flavoured knowledge fact mentioning that NPC by name —
the autonomous-turn prompt lifts the baseline "most turns are routine"
nudge and appends an OPPORTUNITY clause so the LLM can choose in
character whether to act on the moment.

Routine NPCs (peaceful relationships, neutral knowledge) fall
through every gate here and see the unchanged baseline prompt.
"""

from __future__ import annotations

import re
from uuid import UUID

from knowledge.query import KnowledgeQueryEngine
from models.game_state import GameState
from models.npc_card import NPCCard
from models.relationship import Relationship, RelationshipKind
from models.scene import Scene

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

_KNOWLEDGE_KEYWORD_RE = re.compile(
    r"(?:^|[^a-zA-Z])(?:{0})(?:[^a-zA-Z]|$)".format("|".join(KNOWLEDGE_VIOLENCE_KEYWORDS)),
    re.IGNORECASE,
)


def get_opportunity_clause(npc: NPCCard, game_state: GameState) -> str | None:
    """Return a directive OPPORTUNITY clause naming the hostile target, or None.

    When a hostile co-located target is found — via relationship or
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


def _co_located_npc_uuids(scene: Scene, self_npc: NPCCard) -> list[UUID]:
    uuids: list[UUID] = []
    for snpc in scene.npcs_present:
        if snpc.uuid is not None and snpc.uuid != self_npc.uuid:
            uuids.append(snpc.uuid)
    return uuids


def _resolve_hostile_target(
    rel: Relationship,
    co_located_set: set[str],
    game_state: GameState,
) -> str | None:
    if rel.target_uuid not in co_located_set:
        return None
    if rel.kind != RelationshipKind.ENEMY or rel.intensity > -2:
        return None
    try:
        npc_uuid = UUID(rel.target_uuid)
    except ValueError:
        return None
    target_npc = game_state.npcs.get(npc_uuid)
    return target_npc.name if target_npc else None


def _name_from_relationship(
    npc: NPCCard,
    co_located_uuids: list[UUID],
    game_state: GameState,
) -> str | None:
    co_located_set = {str(uid) for uid in co_located_uuids}
    for rel in npc.relationships:
        name = _resolve_hostile_target(rel, co_located_set, game_state)
        if name is not None:
            return name
    return None


def _name_from_knowledge(
    npc: NPCCard,
    co_located_uuids: list[UUID],
    game_state: GameState,
) -> str | None:
    co_located_names = _co_located_display_names(co_located_uuids, game_state)
    if not co_located_names:
        return None
    query_engine = KnowledgeQueryEngine(game_state.knowledge_graph)
    knowledge_text = query_engine.get_context_for_npc(npc)
    if not knowledge_text or not _KNOWLEDGE_KEYWORD_RE.search(knowledge_text):
        return None
    return _names_in_text(co_located_names, knowledge_text)


def _names_in_text(names: list[str], text: str) -> str | None:
    """Return the first name from *names* that appears as a full token in *text*, or None."""
    for candidate in names:
        if not candidate:
            continue
        pattern = r"(?:^|[^a-zA-Z])(?:{0})(?:[^a-zA-Z]|$)".format(re.escape(candidate))
        if re.search(pattern, text, re.IGNORECASE):
            return candidate
    return None


def _co_located_display_names(co_located_uuids: list[UUID], game_state: GameState) -> list[str]:
    """Resolve UUIDs to NPC display names, skipping any not registered in game state."""
    names: list[str] = []
    for uuid in co_located_uuids:
        npc = game_state.npcs.get(uuid)
        if npc is not None:
            names.append(npc.name)
    return names
