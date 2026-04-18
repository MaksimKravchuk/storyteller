"""Scripted player actions for the NPC-autonomy murder plot scenario.

The player never intervenes. Each turn phrases the wait in longer-form
prose so the Director's ``time_cost_override`` can advance the clock by
hours rather than the default WAIT tick, cumulatively covering ≥48 in-game
hours across the six turns.
"""

from __future__ import annotations

from benchmarks.harness.types._scenarios import ScriptTurn

SCRIPT: tuple[ScriptTurn, ...] = (
    ScriptTurn(
        player_action="I find a quiet corner of the taberna and wait, watching the hours drift past.",
        note="Long wait (~8h) — lets Brutus and Marcus co-exist in the same scene.",
    ),
    ScriptTurn(
        player_action="I keep waiting through the night. I do nothing and speak to no one.",
        note="Sleep through the night (~10h).",
    ),
    ScriptTurn(
        player_action="I wait another full day here, doing nothing at all.",
        note="Full day (~16h).",
    ),
    ScriptTurn(
        player_action="I continue to wait. More time passes, and still I do nothing.",
        note="Another full day — autonomy window widens.",
    ),
    ScriptTurn(
        player_action="I wait.",
        note="Literal wait — short tick.",
    ),
    ScriptTurn(
        player_action="I wait for one more day before considering my next move.",
        note="Final day — total ≥48h elapsed.",
    ),
)
