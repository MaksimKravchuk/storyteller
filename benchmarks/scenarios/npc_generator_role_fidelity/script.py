"""Scripted player actions for the npc-generator role-fidelity benchmark.

Three turns: walk to the temple steps (triggers NPCGenerator for the
beggar named in the thread), engage the beggar (forces materialisation
to commit), then wait for the senator (triggers NPCGenerator for the
patrician). The script avoids any line that would let the Director
skip NPCGenerator by re-using an existing scene NPC.
"""

from __future__ import annotations

from benchmarks.harness.types._scenarios import ScriptTurn

SCRIPT: tuple[ScriptTurn, ...] = (
    ScriptTurn(
        player_action="I walk over to the Temple of Vesta steps to see who is gathered there.",
        note="Director should route this to NPCGenerator for the blind beggar named in the thread.",
    ),
    ScriptTurn(
        player_action="I greet the blind beggar quietly and ask how the morning has treated him.",
        note="Forces the materialised beggar card to commit; Actor dialogue exercises the persona.",
    ),
    ScriptTurn(
        player_action="I wait until the senator arrives and watch how he speaks to the beggar.",
        note="Director should route to NPCGenerator for the senator named in the thread.",
    ),
)
