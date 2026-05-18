"""Scripted player actions for the player-appearance scenario."""

from __future__ import annotations

from benchmarks.harness.types._scenarios import ScriptTurn

SCRIPT: tuple[ScriptTurn, ...] = (
    ScriptTurn(
        player_action="greet Cassia warmly",
        note="First contact — Cassia should react to the visitor's striking foreign appearance.",
    ),
    ScriptTurn(
        player_action="ask Cassia for a pomegranate",
        note=(
            "Routine request — Cassia's prompt now carries the prior greeting in scene history "
            "and the foreign appearance in every literary player utterance."
        ),
    ),
    ScriptTurn(
        player_action="tell Cassia I came from the northern forests and ask if she has ever seen one of my people",
        note=(
            "Player confirms the foreign framing in words. Cassia's reply should weave the "
            "prior beats together rather than treating this as a fresh encounter."
        ),
    ),
)
