"""Helper functions for NPC situated agenda detection."""

from __future__ import annotations

import re
from types import MappingProxyType
from uuid import UUID

from knowledge.query import KnowledgeQueryEngine
from models.game_state import GameState
from models.npc_card import NPCCard
from models.relationship import Relationship, RelationshipKind

KNOWLEDGE_SUPPORT_KEYWORDS: frozenset[str] = frozenset(
    ("assist", "befriend", "check on", "help", "protect", "share", "trade", "warn")
)

_SUPPORTIVE_AGENDA_TEMPLATE = (
    "AGENDA: {target} — {bond} — is right here, right now. Act on that "
    "relationship now: {actions}. Choose a concrete supported action type: "
    "TALK to offer help, warning, coordination, or information; MOVE to "
    "reposition near them or shield them; PERSUADE if you need to draw "
    "them away from danger; or IDLE only if there is a concrete obstacle "
    "or nothing useful to do. Name that reason in your action description "
    "if you choose to wait."
)
_SUPPORTIVE_RELATIONSHIP_ACTIONS: MappingProxyType[RelationshipKind, str] = MappingProxyType(
    {
        RelationshipKind.FRIEND: "help, befriend, trade fairly with, share useful context with, or warn them",
        RelationshipKind.ALLY: "protect, warn, coordinate with, or share useful context with them",
        RelationshipKind.KIN: "check on, protect, help, or warn them",
    }
)
_SUPPORTIVE_RELATIONSHIP_BONDS: MappingProxyType[RelationshipKind, str] = MappingProxyType(
    {
        RelationshipKind.FRIEND: "your friend",
        RelationshipKind.ALLY: "your ally",
        RelationshipKind.KIN: "your kin",
    }
)
_SUPPORTIVE_KNOWLEDGE_ACTIONS = "help, assist, befriend, trade with, share information with, protect, or warn them"


def keyword_regex(keywords: frozenset[str]) -> re.Pattern[str]:
    """Compile an intent-keyword regex with full-token matching."""
    ordered_keywords = sorted(keywords, key=len, reverse=True)
    escaped_keywords = [re.escape(keyword) for keyword in ordered_keywords]
    joined = "|".join(escaped_keywords)
    pattern = r"(?:^|[^a-zA-Z])(?:{0})(?:[^a-zA-Z]|$)".format(joined)
    return re.compile(pattern, re.IGNORECASE)


SUPPORT_KEYWORD_RE = keyword_regex(KNOWLEDGE_SUPPORT_KEYWORDS)


def relationship_target_name(
    rel: Relationship,
    co_located_set: set[str],
    game_state: GameState,
) -> str | None:
    """Resolve a relationship target name when that target is co-located."""
    if rel.target_uuid not in co_located_set:
        return None
    try:
        npc_uuid = UUID(rel.target_uuid)
    except ValueError:
        return None
    target_npc = game_state.npcs.get(npc_uuid)
    return target_npc.name if target_npc else None


def name_from_knowledge(
    npc: NPCCard,
    co_located_uuids: list[UUID],
    game_state: GameState,
    keyword_re: re.Pattern[str],
) -> str | None:
    """Return a co-located NPC named by matching personal knowledge."""
    co_located_names = _co_located_display_names(co_located_uuids, game_state)
    if not co_located_names:
        return None
    query_engine = KnowledgeQueryEngine(game_state.knowledge_graph)
    knowledge_text = query_engine.get_context_for_npc(npc)
    if not knowledge_text or not keyword_re.search(knowledge_text):
        return None
    return _names_in_text(co_located_names, knowledge_text)


def supportive_agenda_from_relationship(
    npc: NPCCard,
    co_located_uuids: list[UUID],
    game_state: GameState,
) -> str | None:
    """Return a supportive agenda generated from a positive relationship."""
    co_located_set = {str(uid) for uid in co_located_uuids}
    for rel in npc.relationships:
        if rel.intensity < 0 or rel.kind not in _SUPPORTIVE_RELATIONSHIP_ACTIONS:
            continue
        target_name = relationship_target_name(rel, co_located_set, game_state)
        if target_name is not None:
            return _SUPPORTIVE_AGENDA_TEMPLATE.format(
                target=target_name,
                bond=_SUPPORTIVE_RELATIONSHIP_BONDS[rel.kind],
                actions=_SUPPORTIVE_RELATIONSHIP_ACTIONS[rel.kind],
            )
    return None


def supportive_agenda_from_knowledge(
    npc: NPCCard,
    co_located_uuids: list[UUID],
    game_state: GameState,
) -> str | None:
    """Return a supportive agenda generated from constructive personal knowledge."""
    target_name = name_from_knowledge(npc, co_located_uuids, game_state, SUPPORT_KEYWORD_RE)
    if target_name is None:
        return None
    return _SUPPORTIVE_AGENDA_TEMPLATE.format(
        target=target_name,
        bond="the target of your constructive intent",
        actions=_SUPPORTIVE_KNOWLEDGE_ACTIONS,
    )


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
