"""Implementation of the ``benchmarks narration-diff`` subcommand.

Pairs per-iteration result archives from a previous and a current run by
``scenario_id`` and turn ``index``, then renders a markdown narration diff.
Aggregate ``*_aggregate.json`` files are skipped — they carry no narration.
When the previous directory is absent (e.g. no baseline artifact downloaded
yet), the report degrades gracefully to a current-only listing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from benchmarks.cli._iteration_archives import iter_iteration_files, load_per_iteration_payload
from benchmarks.cli._narration_diff_format import format_report
from benchmarks.cli._narration_diff_model import ScenarioIndex, TurnText

_PATH_NOT_FOUND_EXIT_CODE = 2


def _turns_from_payload(payload: dict[str, Any]) -> list[TurnText]:
    """Extract the ordered list of turns from one per-iteration payload."""
    return [
        TurnText(
            index=raw.get("index", 0),
            player_action=raw.get("player_action", ""),
            narration=raw.get("narration", ""),
        )
        for raw in payload.get("captured_turns", [])
    ]


def build_turn_index(root: Path) -> ScenarioIndex:
    """Map ``scenario_id -> turns`` using the first iteration seen per scenario."""
    index: ScenarioIndex = {}
    for candidate in iter_iteration_files(root):
        payload = load_per_iteration_payload(candidate)
        if payload is None:
            continue
        scenario_id = payload.get("scenario_id")
        if not scenario_id or scenario_id in index:
            continue
        index[scenario_id] = _turns_from_payload(payload)
    return index


def narration_diff_command(args: argparse.Namespace) -> int:
    """Execute the ``narration-diff`` subcommand."""
    current_root = Path(args.current)
    if not current_root.exists():
        sys.stderr.write("Current results path not found: {0}\n".format(current_root))
        return _PATH_NOT_FOUND_EXIT_CODE
    previous_root = Path(args.previous)
    previous_index = build_turn_index(previous_root) if previous_root.exists() else {}
    current_index = build_turn_index(current_root)
    sys.stdout.write("{0}\n".format(format_report(previous_index, current_index)))
    return 0
