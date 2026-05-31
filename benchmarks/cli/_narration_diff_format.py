"""Markdown rendering for the ``benchmarks narration-diff`` subcommand.

The renderer is deterministic and side-effect free: it takes two
``scenario_id -> turns`` indexes (previous and current) and returns a single
markdown string suitable for a PR comment. For prose narration a labelled
``previous`` / ``current`` blockquote pair reads more clearly than a
line-based unified diff, so that is what we emit for changed turns.
"""

from __future__ import annotations

from benchmarks.cli._narration_diff_model import ScenarioIndex, TurnText

_HEADING = "## 📖 Narration diff (previous → current)"
_NO_CURRENT = "_No current results found._"
_NO_BASELINE = "_No baseline content available — first run or no prior artifact._"
_NEW_SCENARIO = "_New scenario — no prior version to compare._"
_UNCHANGED = "_unchanged_"
_NO_PRIOR_TURN = "_no prior turn at this index_"
_REMOVED_TURN = "_turn {0} present in previous version only_"


def _blockquote(label: str, narration: str) -> list[str]:
    """Render a labelled markdown blockquote for one narration body."""
    narration_lines = narration.splitlines() or [""]
    quoted = "\n".join("> {0}".format(line) for line in narration_lines)
    return ["_{0}:_".format(label), quoted]


def _format_turn(previous: TurnText | None, current: TurnText) -> list[str]:
    """Render one current turn against its previous-version counterpart."""
    lines = ["", "**Turn {0}** — `{1}`".format(current.index, current.player_action)]
    if previous is None:
        lines.append(_NO_PRIOR_TURN)
        lines.extend(_blockquote("current", current.narration))
    elif previous.narration == current.narration:
        lines.append(_UNCHANGED)
    else:
        lines.extend(_blockquote("previous", previous.narration))
        lines.extend(_blockquote("current", current.narration))
    return lines


def _previous_by_index(previous_turns: list[TurnText] | None) -> dict[int, TurnText]:
    """Index previous-version turns by their turn index."""
    if previous_turns is None:
        return {}
    return {turn.index: turn for turn in previous_turns}


def _removed_turn_lines(previous_turns: list[TurnText] | None, current: list[TurnText]) -> list[str]:
    """Note turns present in the previous version but absent from the current one."""
    current_indices = {turn.index for turn in current}
    lines: list[str] = []
    for turn in previous_turns or []:
        if turn.index not in current_indices:
            lines.extend(["", _REMOVED_TURN.format(turn.index)])
    return lines


def _format_scenario(
    scenario_id: str,
    previous_turns: list[TurnText] | None,
    current: list[TurnText],
    has_baseline: bool,
) -> list[str]:
    """Render one scenario's per-turn narration diff."""
    lines = ["", "### {0}".format(scenario_id)]
    if has_baseline and previous_turns is None:
        lines.append(_NEW_SCENARIO)
    previous_index = _previous_by_index(previous_turns)
    for turn in current:
        lines.extend(_format_turn(previous_index.get(turn.index), turn))
    lines.extend(_removed_turn_lines(previous_turns, current))
    return lines


def format_report(previous: ScenarioIndex, current: ScenarioIndex) -> str:
    """Render the full markdown narration-diff report."""
    lines = [_HEADING]
    if not current:
        lines.append(_NO_CURRENT)
        return "\n".join(lines)
    has_baseline = bool(previous)
    if not has_baseline:
        lines.append(_NO_BASELINE)
    for scenario_id in sorted(current):
        previous_turns = previous.get(scenario_id)
        current_turns = current[scenario_id]
        lines.extend(_format_scenario(scenario_id, previous_turns, current_turns, has_baseline))
    return "\n".join(lines)
