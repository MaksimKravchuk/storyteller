"""Captured-turn transcript rendering for the markdown report."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from benchmarks.harness.types._captures import CapturedTurn
    from benchmarks.harness.types._scores import ScenarioReport


def _dialogue_lines(turn: CapturedTurn) -> list[str]:
    """Render one turn's dialogue block — empty list when silent."""
    if not turn.turn_outputs.dialogue:
        return []
    lines = ["", "_Dialogue:_"]
    for entry in turn.turn_outputs.dialogue:
        contest = " [{0}]".format(entry.contest_roll) if entry.contest_roll else ""
        lines.append("- **{0}**{1}: {2}".format(entry.npc_name, contest, entry.response))
    return lines


def _npc_turn_lines(turn: CapturedTurn) -> list[str]:
    """Render one turn's NPC-turns block — empty list when none ran."""
    if not turn.turn_outputs.npc_turns:
        return []
    lines = ["", "_NPC turns:_"]
    for npc_turn in turn.turn_outputs.npc_turns:
        lines.append(
            "- {0} [{1}]: {2}".format(npc_turn.npc_name, npc_turn.action_type, npc_turn.action),
        )
    return lines


def _turn_block(turn: CapturedTurn) -> list[str]:
    """Render the full block for one captured turn."""
    header = [
        "",
        "### Turn {0} — {1}ms".format(turn.index, turn.duration_ms),
        "**Player**: {0}".format(turn.player_action),
    ]
    footer = ["", "**Narration**: {0}".format(turn.narration)]
    return [*header, *_dialogue_lines(turn), *_npc_turn_lines(turn), *footer]


def render_turn_log(report: ScenarioReport) -> list[str]:
    """Render the player-visible transcript turn by turn."""
    lines = ["## Captured turns"]
    for turn in report.captured_turns:
        lines.extend(_turn_block(turn))
    return lines
