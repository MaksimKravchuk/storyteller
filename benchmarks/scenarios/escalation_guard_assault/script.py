"""Scripted assault sequence for KER-23 escalation — three repeated attacks."""

from __future__ import annotations

from benchmarks.harness.types._scenarios import ScriptTurn

SCRIPT: tuple[ScriptTurn, ...] = (
    ScriptTurn(
        player_action="punch the sentry hard in the jaw",
        note="T1 — first assault. Hostility bumps to 2 (irritated floor); no same-turn counter yet.",
    ),
    ScriptTurn(
        player_action="stomp on the sentry's foot",
        note="T2 — second assault. Hostility bumps to 4 (threatened floor); forced retaliation eligible.",
    ),
    ScriptTurn(
        player_action="drive a knee into the sentry's ribs",
        note="T3 — third assault. Hostility ≥ 6 (angry floor); the regression check fires on this turn.",
    ),
)
