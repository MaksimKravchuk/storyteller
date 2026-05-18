"""Helpers shared across benchmark scenarios.

Pulls structural duplication (per-turn-NPC-spoke predicates, name
matching, quote-budget constants) out of individual scenarios so a
new scenario's rubric is a list of inputs to existing helpers, not a
re-implementation of the same pattern.
"""

from __future__ import annotations

from dataclasses import dataclass

from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._elements import DeterministicResult
from models.game_state import GameState

EVIDENCE_QUOTE_CHAR_BUDGET = 120


def npc_name_matches(npc_name: str, target: str) -> bool:
    """Return True when ``npc_name`` matches ``target`` after normalisation.

    Case-insensitive comparison with surrounding whitespace stripped —
    matches how scenarios test NPC dialogue ownership uniformly.
    """
    return npc_name.strip().lower() == target.strip().lower()


@dataclass(frozen=True)
class NPCSpeaksOn:
    """Deterministic predicate: a named NPC emits a dialogue entry on ``turn_index``.

    Replaces per-scenario ``_FooSpeaksOn`` dataclasses that only
    differed in the NPC name they matched against. Awards 1 point on
    success and stamps the reply's prefix as ``evidence_quote`` for
    the run report.
    """

    npc_name: str
    turn_index: int

    def __call__(
        self,
        captured: list[CapturedTurn],
        _snapshots: list[GameState],
    ) -> DeterministicResult:
        if self.turn_index >= len(captured):
            return DeterministicResult(
                awarded=0,
                reason="turn {0} was not captured".format(self.turn_index),
            )
        dialogue = captured[self.turn_index].turn_outputs.dialogue
        entries = [entry for entry in dialogue if npc_name_matches(entry.npc_name, self.npc_name)]
        if not entries:
            return DeterministicResult(
                awarded=0,
                reason="no dialogue entry from {0} on turn {1}".format(self.npc_name, self.turn_index),
            )
        quote = entries[0].response[:EVIDENCE_QUOTE_CHAR_BUDGET]
        return DeterministicResult(
            awarded=1,
            reason="{0} replied on turn {1}".format(self.npc_name, self.turn_index),
            evidence_quote=quote,
        )
