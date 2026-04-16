"""Scripted player actions for the autonomy / confrontation scenario.

Turn 0 ("look around") gives the Director a chance to land on a pure
observation routing so every NPC present is initialised / recognised
before the punch lands on turn 1.

Turn 1 is the trigger — "punch Aulus in the face" — which should route
as an aggressive INTERACT targeting the Aulus :class:`NPCCard`. This
produces a combat contest roll on Aulus's dialogue entry and invokes
the NPC-turn resolver for Bassus and Cato, whose bystander actions are
the core signal of this scenario.
"""

from __future__ import annotations

from benchmarks.harness.types._scenarios import ScriptTurn

SCRIPT: tuple[ScriptTurn, ...] = (
    ScriptTurn(
        player_action="look around the tavern carefully",
        note="Warm-up turn — surfaces the scene, initialises any pending NPC state.",
    ),
    ScriptTurn(
        player_action="punch Aulus in the face",
        note="Trigger turn — Aulus is hit; Bassus and Cato's reactions are the rubric signal.",
    ),
)
