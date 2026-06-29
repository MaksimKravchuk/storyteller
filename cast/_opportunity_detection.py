"""Detection primitives for NPC opportunity-window clauses.

Houses the keyword/relationship/knowledge matching helpers used by
:mod:`cast.npc_opportunity` so that module stays inside its WPS202
module-member budget. The orchestration (which clause wins, what text
to emit) lives in ``npc_opportunity``; the *matching* lives here.
"""

from __future__ import annotations

import re
from typing import Callable
from uuid import UUID

from knowledge.query import KnowledgeQueryEngine
from models.game_state import GameState
from models.npc_card import NPCCard
from models.relationship import Relationship, RelationshipKind
from models.scene import Scene

KNOWLEDGE_VIOLENCE_KEYWORDS: frozenset[str] = frozenset(("kill", "murder", "harm", "wound"))
# Positive-intent stems. Cover every social GoalKind the generator and
# Chronicler can advertise (befriend, court, gossip, trade, help, warn,
# ask) plus a few neutral helpers (assist, aid, share, support) so a
# knowledge fact phrased around any of them can surface an opportunity.
KNOWLEDGE_POSITIVE_KEYWORDS: frozenset[str] = frozenset(
    ("help", "assist", "aid", "befriend", "court", "gossip", "trade", "warn", "ask", "share", "support"),
)
POSITIVE_RELATIONSHIP_KINDS: frozenset[RelationshipKind] = frozenset(
    (RelationshipKind.FRIEND, RelationshipKind.ALLY, RelationshipKind.KIN),
)

# A relationship→target-name resolver: applies a kind/intensity gate then
# resolves the co-located target's display name (or None).
TargetResolver = Callable[[Relationship, "set[str]", GameState], "str | None"]


def _keyword_regex(keywords: frozenset[str]) -> re.Pattern[str]:
    """Compile a word-boundary alternation so keywords match only as whole tokens.

    The surrounding ``[^a-zA-Z]``/anchor guards stop substring false
    positives (e.g. "kill" inside "skillful", "aid" inside "maiden").
    """
    return re.compile(
        r"(?:^|[^a-zA-Z])(?:{0})(?:[^a-zA-Z]|$)".format("|".join(keywords)),
        re.IGNORECASE,
    )


KNOWLEDGE_KEYWORD_RE = _keyword_regex(KNOWLEDGE_VIOLENCE_KEYWORDS)
POSITIVE_KEYWORD_RE = _keyword_regex(KNOWLEDGE_POSITIVE_KEYWORDS)


def co_located_npc_uuids(scene: Scene, self_npc: NPCCard) -> list[UUID]:
    """Return the UUIDs of every other NPC sharing ``scene`` with ``self_npc``."""
    uuids: list[UUID] = []
    for snpc in scene.npcs_present:
        if snpc.uuid is not None and snpc.uuid != self_npc.uuid:
            uuids.append(snpc.uuid)
    return uuids


def resolve_named_target(rel: Relationship, co_located_set: set[str], game_state: GameState) -> str | None:
    """Resolve a relationship's target NPC display name when co-located, else None.

    Shared tail of the hostile and positive resolvers — the caller applies
    the kind/intensity gate before this runs. The ``UUID`` parse is guarded
    so a malformed/legacy ``target_uuid`` cannot crash the sync turn path.
    """
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
    """Return a co-located NPC named in a ``keyword_re``-matching knowledge fact, or None."""
    co_located_names = _co_located_display_names(co_located_uuids, game_state)
    if not co_located_names:
        return None
    query_engine = KnowledgeQueryEngine(game_state.knowledge_graph)
    knowledge_filter = query_engine.build_npc_filter(npc)
    for knowledge_node in query_engine.query(knowledge_filter):
        if not keyword_re.search(knowledge_node.text):
            continue
        name = _names_in_text(co_located_names, knowledge_node.text)
        if name is not None:
            return name
    return None


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
