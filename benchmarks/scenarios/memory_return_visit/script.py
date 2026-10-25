"""Scripted player actions for the return-visit memory scenario.

Mirrors the 2026-10-25 production report: the player tells Eira who they
are and who they are looking for, walks away up the village path, walks
back to the landing and asks her to recall it. Before the place-persistence
fix every MOVE regenerated the landing's NPCs, so a stranger answered.
"""

from __future__ import annotations

from benchmarks.harness.types._scenarios import ScriptTurn

RECALL_TURN_INDEX = 3

SCRIPT: tuple[ScriptTurn, ...] = (
    ScriptTurn(
        player_action=(
            'I walk up to Eira at the net. "Good evening, Eira. My name is Elias Grey. I am searching for my '
            "brother Tomas — a thin man with a red woollen scarf. He sailed from here three days ago on a boat "
            'called the Gull and never came back."'
        ),
        note="Seed the facts Eira must later recall: name, brother, scarf, boat.",
    ),
    ScriptTurn(
        player_action="I thank Eira and walk up the narrow path between the turf-roofed houses, away from the shore.",
        note="Leave the landing — a new place, scene rebuild.",
    ),
    ScriptTurn(
        player_action="I walk back down the path to the landing where Eira mends her net.",
        note="Return — the landing must be the same place, with the same Eira in it.",
    ),
    ScriptTurn(
        player_action=(
            '"Eira, do you remember me? What is my name, who am I looking for, what was he wearing, '
            'and what was his boat called?"'
        ),
        note="Recall check — Eira should answer from memory of the first conversation.",
    ),
)
