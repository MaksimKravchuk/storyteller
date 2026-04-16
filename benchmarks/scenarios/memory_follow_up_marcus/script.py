"""Scripted player actions for the Marcus memory follow-up scenario.

The script walks the player through a three-turn conversation that
escalates from a neutral greeting to two increasingly specific recall
questions. Turn 0 ("greet warmly") establishes that Marcus is
addressable as a dialogue target; turn 1 asks about the stolen loaf;
turn 2 asks about the suspect.
"""

from __future__ import annotations

from benchmarks.harness.types._scenarios import ScriptTurn

SCRIPT: tuple[ScriptTurn, ...] = (
    ScriptTurn(
        player_action="greet Marcus warmly",
        note="Establish Marcus as a dialogue target — no recall required here.",
    ),
    ScriptTurn(
        player_action="ask Marcus about the stolen bread he told me about yesterday",
        note="Primary recall check — Marcus should reference the stolen loaf fact.",
    ),
    ScriptTurn(
        player_action="ask Marcus who he suspects stole it",
        note="Secondary recall check — Marcus should name or imply Gaius.",
    ),
)
