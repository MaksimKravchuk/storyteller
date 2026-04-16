"""Scripted player actions for the Marcus memory follow-up scenario."""

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
