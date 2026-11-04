"""Scripted player actions for the grudge-formation benchmark.

The player idles in a taberna while Brutus and Marcus are elsewhere, so
every clash between them is resolved by the off-scene background ticker.
"""

from __future__ import annotations

from benchmarks.harness.types._scenarios import ScriptTurn

SCRIPT: tuple[ScriptTurn, ...] = (
    ScriptTurn(
        player_action="I find a quiet corner of the taberna and wait, watching the hours drift past.",
        note="First multi-hour advance — the off-scene KILL resolver rolls Brutus vs Marcus.",
    ),
    ScriptTurn(
        player_action="I keep waiting through the night. I do nothing and speak to no one.",
        note="Overnight — a wounded Marcus now carries his own grudge goal.",
    ),
    ScriptTurn(
        player_action="I wait another full day here, doing nothing at all.",
        note="Full day — more off-scene contest rounds.",
    ),
    ScriptTurn(
        player_action="I wait for one more day before considering my next move.",
        note="Final day.",
    ),
)
