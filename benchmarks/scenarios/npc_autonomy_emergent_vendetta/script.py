"""Scripted player actions for the emergent-vendetta benchmark.

Same shape as :mod:`benchmarks.scenarios.npc_autonomy_murder_plot.script`:
the player never intervenes; six prose-WAIT turns advance the in-game
clock past 48 hours so the World Chronicler is invoked multiple times
and the off-scene background ticker has room to roll contests.
"""

from __future__ import annotations

from benchmarks.harness.types._scenarios import ScriptTurn

SCRIPT: tuple[ScriptTurn, ...] = (
    ScriptTurn(
        player_action="I find a quiet corner of the taberna and wait, watching the hours drift past.",
        note="First Chronicler invocation — the goal_drafts channel should fire here if at all.",
    ),
    ScriptTurn(
        player_action="I keep waiting through the night. I do nothing and speak to no one.",
        note="Sleep through the night (~10h).",
    ),
    ScriptTurn(
        player_action="I wait another full day here, doing nothing at all.",
        note="Full day (~16h) — promotion + on-scene clash window.",
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
