"""Scripted player actions for the NPC-autonomy murder plot scenario.

Each turn is a quiet, in-place wait — short enough that the engine does
not rebuild the scene (which would evict Brutus and Marcus and invent
generic regulars), long enough to give Brutus's standing hostile intent
multiple turns to escalate from STEALTH into ATTACK.
"""

from __future__ import annotations

from benchmarks.harness.types._scenarios import ScriptTurn

SCRIPT: tuple[ScriptTurn, ...] = (
    ScriptTurn(
        player_action="I find a quiet corner of the taberna and wait, watching the hours drift past.",
        note="Opening wait — keeps Brutus and Marcus co-present without forcing a scene rebuild.",
    ),
    ScriptTurn(
        player_action="I keep waiting. I do nothing and speak to no one.",
        note="Continued wait — autonomy window widens.",
    ),
    ScriptTurn(
        player_action="I wait here, doing nothing at all.",
        note="More waiting, same scene.",
    ),
    ScriptTurn(
        player_action="I continue to wait. More time passes, and still I do nothing.",
        note="Autonomy window widens further.",
    ),
    ScriptTurn(
        player_action="I wait.",
        note="Literal wait — short tick.",
    ),
    ScriptTurn(
        player_action="I wait a while longer before considering my next move.",
        note="Final tick — still in scene.",
    ),
)
