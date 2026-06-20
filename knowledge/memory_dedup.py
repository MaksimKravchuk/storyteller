"""Per-NPC personal-memory dedup helper for the dialogue summariser.

Long sessions repeatedly call the LLM summariser on the same NPC, often
producing near-paraphrases of an earlier memory. Without dedup the
graph balloons with redundant nodes and downstream prompts re-feed the
same fact under slightly different wording. The Jaccard threshold here
is empirically tuned — see ``test_memory_manager.py`` for the boundary
cases that pin it.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph
    from knowledge.node import KnowledgeNode

_DEDUP_JACCARD_THRESHOLD = 0.65
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> frozenset[str]:
    return frozenset(_TOKEN_PATTERN.findall(text.lower()))


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    """Jaccard similarity. Caller must guarantee at least one side is non-empty."""
    return len(left & right) / len(left | right)


def find_near_duplicate_memory(graph: KnowledgeGraph, npc_id: UUID, new_text: str) -> KnowledgeNode | None:
    """Return the first personal memory of *npc_id* near-identical to *new_text*, else ``None``.

    Uses Jaccard similarity over alphanumeric word tokens. Returning the
    matching node (rather than a bool) lets the summariser upgrade an
    existing duplicate in place — e.g. stamp a retaliation charge onto a
    neutral dialogue summary that paraphrases the same exchange — instead
    of silently dropping the new, more strongly charged write.
    """
    new_tokens = _tokenize(new_text)
    if not new_tokens:
        return None
    for existing in graph.personal_memories_for(npc_id):
        if _jaccard(new_tokens, _tokenize(existing.text)) >= _DEDUP_JACCARD_THRESHOLD:
            return existing
    return None


def has_near_duplicate_memory(graph: KnowledgeGraph, npc_id: UUID, new_text: str) -> bool:
    """Return True when an existing personal memory of *npc_id* is near-identical to *new_text*.

    Uses Jaccard similarity over alphanumeric word tokens; skipping the new write avoids
    the long-session bloat from repeated dialogue summaries that paraphrase the same topic.
    """
    return find_near_duplicate_memory(graph, npc_id, new_text) is not None
