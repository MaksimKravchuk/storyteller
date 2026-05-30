"""Scripted player actions for the world-gen vividness benchmark.

Two turns: enter and take in the street (Scene-Builder + Narrator render the
locale from the seeded setting), then greet a wool merchant (Director →
NPCGenerator produces a character who should belong to the seeded social
structure). Both turns give the rubric era-grounded prose to judge.
"""

from __future__ import annotations

from benchmarks.harness.types._scenarios import ScriptTurn

SCRIPT: tuple[ScriptTurn, ...] = (
    ScriptTurn(
        player_action="I walk into the wool-merchants' street and take in the workshops and the crowd.",
        note="Scene-build path — Narrator renders the locale from the seeded Florence setting.",
    ),
    ScriptTurn(
        player_action="I approach the nearest wool merchant at his bench and greet him.",
        note="NPC path — the generated trader should reflect the seeded guild social structure.",
    ),
)
