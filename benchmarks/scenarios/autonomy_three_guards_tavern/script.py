"""Scripted player actions for the autonomy / confrontation scenario."""

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
