"""Scripted player actions for the narrator-prose quiet-exploration benchmark.

Three turns of solo, NPC-free activity: enter and look, interact with
a single object, then stand still. Each turn gives the Narrator a
different prompt shape (scene-build, object interaction, pure wait)
so the rubric exercises prose across the three Narrator code paths.
"""

from __future__ import annotations

from benchmarks.harness.types._scenarios import ScriptTurn

SCRIPT: tuple[ScriptTurn, ...] = (
    ScriptTurn(
        player_action="I step into the atrium and look around slowly.",
        note="Scene-build path — Narrator renders the initial location prose.",
    ),
    ScriptTurn(
        player_action="I walk to the impluvium and trail my fingers in the water.",
        note="Object-interaction path — single-POI focus, no new locale.",
    ),
    ScriptTurn(
        player_action="I stand still and listen to the night.",
        note="Pure-wait path — atmospheric only, no concrete action.",
    ),
)
