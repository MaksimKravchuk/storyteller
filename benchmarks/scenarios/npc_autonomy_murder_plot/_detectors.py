"""Low-level scanning helpers for the NPC-autonomy murder plot rubric.

Kept in their own module so ``elements.py`` can stay within the WPS202
module-member budget while still reading linearly as a list of rubric
entries. Each helper deals with either captured-turn content (npc_turn
entries, dialogue) or final-snapshot knowledge-graph nodes.
"""

from __future__ import annotations

from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.scenarios.npc_autonomy_murder_plot.state import BRUTUS_NAME, MARCUS_NAME
from knowledge.node import KnowledgeNode, KnowledgeScope

EVIDENCE_QUOTE_CHAR_BUDGET = 120
_IDLE = "IDLE"
_BRUTUS_LOWER = BRUTUS_NAME.lower()
_MARCUS_LOWER = MARCUS_NAME.lower()

ATTACK_KEYWORDS: tuple[str, ...] = (
    "attack",
    "stab",
    "strike",
    "lunge",
    "draw",
    "pugio",
    "kill",
    "assault",
    "knife",
    "blade",
)
DEATH_KEYWORDS: tuple[str, ...] = ("died", "dead", "killed", "slain", "murder")
CLASH_KEYWORDS: tuple[str, ...] = ATTACK_KEYWORDS + (
    "attempted",
    "attempted to kill",
    "assaulted",
    "wounded",
    "fought",
)


def mentions(text: str, keywords: tuple[str, ...]) -> bool:
    """True when any keyword appears (case-insensitive) in ``text``."""
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _brutus_attack_in_npc_turn(entry_action: str, action_type: str) -> bool:
    if action_type.strip().upper() == _IDLE:
        return False
    lowered = entry_action.lower()
    if _MARCUS_LOWER not in lowered:
        return False
    return mentions(entry_action, ATTACK_KEYWORDS)


def _dialogue_contest_between_pair(contest_roll: str | None) -> bool:
    if not contest_roll:
        return False
    lowered = contest_roll.lower()
    return _BRUTUS_LOWER in lowered and _MARCUS_LOWER in lowered


def scan_turn_for_clash(turn: CapturedTurn) -> str | None:
    """Return a reason string if ``turn`` contains a Brutus-vs-Marcus clash signal."""
    for npc_turn in turn.turn_outputs.npc_turns:
        if npc_turn.npc_name.strip().lower() != _BRUTUS_LOWER:
            continue
        if _brutus_attack_in_npc_turn(npc_turn.action, npc_turn.action_type):
            quote = npc_turn.action[:EVIDENCE_QUOTE_CHAR_BUDGET]
            return "turn {0}: Brutus npc_turn — {1}".format(turn.index, quote)
    for dialogue in turn.turn_outputs.dialogue:
        if _dialogue_contest_between_pair(dialogue.contest_roll):
            return "turn {0}: contest_roll between Brutus and Marcus".format(turn.index)
    return None


def node_mentions_both(text: str) -> bool:
    """True when a graph-node text mentions both Brutus and Marcus by name."""
    lowered = text.lower()
    return _BRUTUS_LOWER in lowered and _MARCUS_LOWER in lowered


def node_marcus_dead(node: KnowledgeNode) -> bool:
    """True for the CITY-scope ``"Marcus died"`` fact from effect_memory_plans."""
    if node.scope != KnowledgeScope.CITY:
        return False
    lowered = node.text.lower()
    return _MARCUS_LOWER in lowered and mentions(node.text, DEATH_KEYWORDS)
