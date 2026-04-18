"""Knowledge-graph node predicates for the murder-plot rubric.

Separated from ``_detectors`` so each module stays within the WPS202
public-member budget. All three predicates operate on a single
``KnowledgeNode`` and are used by ``_outcome_recorded_in_world_facts``
to classify session-added nodes.
"""

from __future__ import annotations

from benchmarks.scenarios.npc_autonomy_murder_plot._detectors import mentions
from benchmarks.scenarios.npc_autonomy_murder_plot.state import BRUTUS_NAME, MARCUS_NAME
from knowledge.node import KnowledgeNode, KnowledgeScope

_BRUTUS_LOWER = BRUTUS_NAME.lower()
_MARCUS_LOWER = MARCUS_NAME.lower()
_DEATH_KEYWORDS: tuple[str, ...] = ("died", "dead", "killed", "slain", "murder")


def node_mentions_both(text: str) -> bool:
    """True when a graph-node text mentions both Brutus and Marcus by name."""
    lowered = text.lower()
    return _BRUTUS_LOWER in lowered and _MARCUS_LOWER in lowered


def _node_participant_died(node: KnowledgeNode, participant_name_lower: str) -> bool:
    if node.scope != KnowledgeScope.CITY:
        return False
    lowered = node.text.lower()
    return participant_name_lower in lowered and mentions(node.text, _DEATH_KEYWORDS)


def node_marcus_dead(node: KnowledgeNode) -> bool:
    """True for a CITY-scope ``"Marcus died"`` fact (target-death resolution)."""
    return _node_participant_died(node, _MARCUS_LOWER)


def node_brutus_dead(node: KnowledgeNode) -> bool:
    """True for a CITY-scope ``"Brutus died"`` fact (attacker-death resolution)."""
    return _node_participant_died(node, _BRUTUS_LOWER)
