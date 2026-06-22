"""Scripted player actions for the social-befriend autonomy benchmark.

Same shape as the sister autonomy scenarios: the player never
intervenes; several prose-WAIT turns give Drusilla room to act on her
BEFRIEND goal autonomously while the clock advances.
"""

from __future__ import annotations

from benchmarks.harness.types._scenarios import ScriptTurn

SCRIPT: tuple[ScriptTurn, ...] = (
    ScriptTurn(
        player_action="I find a quiet corner of the taberna and wait, watching the hours drift past.",
        note="First autonomy window — Drusilla should begin pursuing her BEFRIEND goal here.",
    ),
    ScriptTurn(
        player_action="I keep to myself and let the afternoon pass, speaking to no one.",
        note="Drusilla has more time alone with Livia in the room.",
    ),
    ScriptTurn(
        player_action="I wait another while, doing nothing at all.",
        note="Wider autonomy window — repeated social approach expected, not violence.",
    ),
    ScriptTurn(
        player_action="I continue to wait. More time passes, and still I do nothing.",
        note="Drusilla keeps pursuing the friendship in character.",
    ),
    ScriptTurn(
        player_action="I wait for a little longer before considering my next move.",
        note="Final idle turn.",
    ),
)
