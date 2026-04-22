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

OPPORTUNITY_CLAUSE = (
    "OPPORTUNITY: The scene gives you a rare opening toward a standing personal goal. "
    "Inaction is itself a choice to let the moment pass. Decide in character — "
    "do not force a confrontation that is not yours, but do not pretend the "
    "opening is not there either."
)


def _compile_keyword_re(keywords: frozenset[str]) -> re.Pattern[str]:
    r"""Compile a keyword set into a full-token match regex.

    Uses ``[^a-zA-Z]`` instead of Python's default ``\b`` because ``\b``
    treats ``_`` as a word character — so ``\bkill\b`` fails to match
    inside a label like ``"murderous_enemy"`` even though ``kill`` is a
    full token separated by non-alphabetic characters. The alphabetic-
    neighbour rejection still keeps ``"skillful"`` from firing on
    ``"kill"`` and ``"pharmacist"`` from firing on ``"harm"``.
    """
    pattern = r"(?:^|[^a-zA-Z])(?:{0})(?:[^a-zA-Z]|$)".format("|".join(keywords))
    return re.compile(pattern, re.IGNORECASE)


_RELATIONSHIP_KEYWORD_RE = _compile_keyword_re(RELATIONSHIP_HOSTILITY_KEYWORDS)
_KNOWLEDGE_KEYWORD_RE = _compile_keyword_re(KNOWLEDGE_VIOLENCE_KEYWORDS)


def detect_opportunity(npc: NPCCard, game_state: GameState) -> bool:
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


def _co_located_npc_uuids(scene: Scene, self_npc: NPCCard) -> list[str]:
    uuids: list[str] = []
    for snpc in scene.npcs_present:
        if snpc.uuid and snpc.uuid != self_npc.uuid:
            uuids.append(snpc.uuid)
    return uuids


def _has_hostile_relationship_co_located(npc: NPCCard, co_located_uuids: list[str]) -> bool:
    co_located_set = set(co_located_uuids)
    for target_uuid, label in npc.relationships.items():
        if target_uuid in co_located_set and _RELATIONSHIP_KEYWORD_RE.search(label or ""):
            return True
    return False


def _has_violent_knowledge_mentioning_co_located(
    npc: NPCCard,
    co_located_uuids: list[str],
    game_state: GameState,
) -> bool:
    co_located_names = _co_located_display_names(co_located_uuids, game_state)
    if not co_located_names:
        return False
    knowledge_text = _load_knowledge_text(npc, game_state)
    if not knowledge_text or not _KNOWLEDGE_KEYWORD_RE.search(knowledge_text):
        return False
    lowered = knowledge_text.lower()
    return any(name and name.lower() in lowered for name in co_located_names)


def _co_located_display_names(co_located_uuids: list[str], game_state: GameState) -> list[str]:
    """Resolve UUIDs to NPC display names, skipping any not registered in game state."""
    names: list[str] = []
    for uuid in co_located_uuids:
        npc = game_state.npcs.get(uuid)
        if npc is not None:
            names.append(npc.name)
    return names


def _load_knowledge_text(npc: NPCCard, game_state: GameState) -> str:
    query_engine = KnowledgeQueryEngine(game_state.knowledge_graph)
    return query_engine.get_context_for_npc(npc, topic_tags=None)
