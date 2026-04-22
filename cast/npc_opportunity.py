"""KER-42 opportunity-window detection for NPC autonomous turns.

When an NPC shares a scene with someone they have a standing hostile
goal toward — encoded either as a hostility-flavoured relationship label
or as a violence-flavoured knowledge fact mentioning that NPC by name —
the autonomous-turn prompt lifts the baseline "most turns are routine"
nudge and appends an OPPORTUNITY clause so the LLM can choose in
character whether to act on the moment.

Routine NPCs (empty / peaceful relationships, neutral knowledge) fall
through every gate here and see the unchanged baseline prompt.
"""

from __future__ import annotations

from typing import Any

from knowledge.query import KnowledgeQueryEngine
from models.game_state import GameState

# Relationship labels or knowledge-fact keywords that signal a standing
# goal to harm a named target. Matched as case-insensitive substrings —
# tolerant to morphology ("murderous_enemy", "sworn rival", "to kill him").
RELATIONSHIP_HOSTILITY_KEYWORDS: frozenset[str] = frozenset(
    (
        "kill",
        "murder",
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

OPPORTUNITY_CLAUSE = (
    "OPPORTUNITY: The scene gives you a rare opening toward a standing personal goal. "
    "Inaction is itself a choice to let the moment pass. Decide in character — "
    "do not force a confrontation that is not yours, but do not pretend the "
    "opening is not there either."
)


def detect_opportunity(npc: Any, game_state: GameState) -> bool:
    """Return True when the opportunity-window gate fires for *npc* this scene."""
    scene = game_state.current_scene
    if scene is None:
        return False
    co_located = _co_located_npc_uuids(scene, npc)
    if not co_located:
        return False
    if _has_hostile_relationship_co_located(npc, co_located):
        return True
    return _has_violent_knowledge_mentioning_co_located(npc, co_located, game_state)


def _co_located_npc_uuids(scene: Any, self_npc: Any) -> list[str]:
    """Return UUIDs of every other NPC present in the scene."""
    uuids: list[str] = []
    for snpc in scene.npcs_present:
        if snpc.uuid and snpc.uuid != self_npc.uuid:
            uuids.append(snpc.uuid)
    return uuids


def _has_hostile_relationship_co_located(npc: Any, co_located_uuids: list[str]) -> bool:
    """Return True if the NPC has a hostile-labelled relationship with someone in the scene."""
    relationships = getattr(npc, "relationships", None) or {}
    co_located_set = set(co_located_uuids)
    for target_uuid, label in relationships.items():
        if target_uuid in co_located_set and _contains_keyword(label, RELATIONSHIP_HOSTILITY_KEYWORDS):
            return True
    return False


def _has_violent_knowledge_mentioning_co_located(
    npc: Any,
    co_located_uuids: list[str],
    game_state: GameState,
) -> bool:
    """Return True if this NPC's accessible knowledge names a co-located NPC and a violence keyword."""
    co_located_names = _co_located_display_names(co_located_uuids, game_state)
    if not co_located_names:
        return False
    lowered = _load_knowledge_text(npc, game_state).lower()
    if not lowered:
        return False
    if not any(keyword in lowered for keyword in KNOWLEDGE_VIOLENCE_KEYWORDS):
        return False
    return any(name.lower() in lowered for name in co_located_names)


def _co_located_display_names(co_located_uuids: list[str], game_state: GameState) -> list[str]:
    """Resolve UUIDs to NPC display names, skipping any not registered in game state."""
    names: list[str] = []
    for uuid in co_located_uuids:
        npc = game_state.npcs.get(uuid)
        if npc is not None:
            names.append(npc.name)
    return names


def _load_knowledge_text(npc: Any, game_state: GameState) -> str:
    query_engine = KnowledgeQueryEngine(game_state.knowledge_graph)
    return query_engine.get_context_for_npc(npc, topic_tags=None)


def _contains_keyword(haystack: str, keywords: frozenset[str]) -> bool:
    if not haystack:
        return False
    lowered = haystack.lower()
    return any(keyword in lowered for keyword in keywords)
