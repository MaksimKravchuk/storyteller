"""Scripted player actions for the scene-builder re-entry-consistency benchmark.

Four turns: a first look at the Forum (anchors the seeded POIs in the
Narrator's first prose), a transition out to the Vicus Tuscus, a beat
in the side street, and a return to the Forum that forces a second
SceneBuilder pass. The deterministic checks then compare the Forum's
POI list across the round trip.
"""

from __future__ import annotations

from benchmarks.harness.types._scenarios import ScriptTurn

SCRIPT: tuple[ScriptTurn, ...] = (
    ScriptTurn(
        player_action="I survey the Forum Romanum from the centre, taking in the landmarks around me.",
        note="First Forum scene-build — anchors rostra, Temple of Saturn, Basilica Julia in prose.",
    ),
    ScriptTurn(
        player_action="I walk south down the Vicus Tuscus.",
        note="Scene transition — new SceneBuilder pass for the side street.",
    ),
    ScriptTurn(
        player_action="I linger on the Vicus Tuscus for a moment, watching the shopkeepers.",
        note="Beat in the new locale so the player has clearly left the Forum.",
    ),
    ScriptTurn(
        player_action="I head back to the Forum Romanum and look around again.",
        note="Re-entry — second SceneBuilder pass over the Forum; POI list must persist.",
    ),
)
