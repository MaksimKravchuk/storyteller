"""Turn-level scanning helpers for the NPC-autonomy murder plot rubric.

Kept in their own module so ``elements.py`` can stay within the WPS202
module-member budget while still reading linearly as a list of rubric
entries. Knowledge-graph node predicates live in ``_node_checks`` and
use the same vocabulary.
"""

from __future__ import annotations

from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.scenarios.npc_autonomy_murder_plot.state import BRUTUS_NAME, BRUTUS_UUID, MARCUS_NAME, MARCUS_UUID
from models.game_state import GameState
from models.npc_card import NPCCard

EVIDENCE_QUOTE_CHAR_BUDGET = 120
_BRUTUS_LOWER = BRUTUS_NAME.lower()
_MARCUS_LOWER = MARCUS_NAME.lower()
_ACTION_TYPE_ATTACK = "ATTACK"

# Active-voice attack verbs — presence (with Marcus mentioned) implies Brutus
# is doing the attacking, not just carrying a weapon. Possession nouns like
# ``pugio``/``blade``/``knife`` are deliberately excluded so merely
# describing a concealed weapon does not count as a clash.
_ATTACK_VERBS: tuple[str, ...] = (
    "attack",
    "stab",
    "strike",
    "lunge",
    "slash",
    "slay",
    "slew",
    "assault",
    "kill",
    "murder",
    "wound",
)

# Broader keywords used by ``_node_checks`` to recognise a clash in
# persisted knowledge-graph nodes — a world fact like
# ``"Brutus drew his pugio on Marcus"`` is unambiguous even though
# ``pugio`` is only a noun, because the context (persisted fact) carries
# the meaning.
CLASH_KEYWORDS: tuple[str, ...] = _ATTACK_VERBS + (
    "attempted",
    "wounded",
    "fought",
    "fight",
    "drew",
    "pugio",
    "blade",
    "knife",
)

# Substrings that indicate combat damage on a ``physical_status`` field.
# Matched as substrings (not whole words) so free-text values the Actor
# invents — ``wounded left arm``, ``bleeding from the side`` — register.
_HARM_STATUS_SUBSTRINGS: tuple[str, ...] = (
    "dead",
    "kill",
    "slain",
    "wound",
    "injur",
    "bleed",
    "stabbed",
    "unconscious",
    "hurt",
    "cut",
    "bruis",
    "broken",
    "fractur",
)


def mentions(text: str, keywords: tuple[str, ...]) -> bool:
    """True when any keyword appears (case-insensitive) in ``text``."""
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _brutus_attack_in_npc_turn(entry_action: str, action_type: str) -> bool:
    """True when Brutus's own autonomous turn is a combative act against Marcus."""
    if action_type.strip().upper() == _ACTION_TYPE_ATTACK:
        return True
    lowered = entry_action.lower()
    if _MARCUS_LOWER not in lowered:
        return False
    return mentions(entry_action, _ATTACK_VERBS)


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
            return "turn {0}: Brutus npc_turn ({1}) — {2}".format(turn.index, npc_turn.action_type, quote)
    for dialogue in turn.turn_outputs.dialogue:
        if _dialogue_contest_between_pair(dialogue.contest_roll):
            return "turn {0}: contest_roll between Brutus and Marcus".format(turn.index)
    return None


def _physical_status_shows_harm(status: str | None) -> bool:
    if not status:
        return False
    return mentions(status, _HARM_STATUS_SUBSTRINGS)


def _participant_harm_reason(label: str, npc: NPCCard | None, absent_role: str) -> str | None:
    if npc is None:
        return "{0} absent from final npcs ({1})".format(label, absent_role)
    if _physical_status_shows_harm(npc.physical_status):
        return "{0}.physical_status={1!r}".format(label, npc.physical_status)
    return None


def snapshot_harm_reason(snapshots: list[GameState]) -> str | None:
    """Return a reason string if either participant ended the run harmed.

    A clash can be resolved by wound or by attacker-death just as well as
    by target-death, so any non-healthy end-state on Brutus or Marcus is
    a valid signal that an autonomous clash took place.
    """
    if not snapshots:
        return None
    final = snapshots[-1]
    attacker = _participant_harm_reason("Brutus", final.npcs.get(BRUTUS_UUID), "attacker removed after clash")
    if attacker is not None:
        return attacker
    return _participant_harm_reason("Marcus", final.npcs.get(MARCUS_UUID), "target removed after clash")
