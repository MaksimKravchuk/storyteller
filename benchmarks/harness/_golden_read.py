"""No-LLM read / compare helpers for golden narration snapshot checks."""

from __future__ import annotations

import json
from difflib import unified_diff
from pathlib import Path
from typing import TYPE_CHECKING, Mapping, Sequence

from benchmarks.cli._narration_diff_model import ScenarioIndex, TurnText

if TYPE_CHECKING:
    from benchmarks.harness.types._captures import CapturedTurn

DEFAULT_GOLDEN_DIR = Path(__file__).resolve().parents[1] / "golden"
SCHEMA_VERSION = 1


def snapshot_from_turns(scenario_id: str, turns: Sequence[CapturedTurn]) -> dict[str, object]:
    """Build a stable golden snapshot payload from captured benchmark turns."""
    return {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": scenario_id,
        "turns": [
            {"index": turn.index, "player_action": turn.player_action, "narration": turn.narration} for turn in turns
        ],
    }


def serialise_snapshot(payload: Mapping[str, object]) -> str:
    """Render canonical JSON bytes for reviewable golden snapshots."""
    return "{0}\n".format(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


def load_narration_index(root: Path) -> ScenarioIndex:
    """Load ``scenario_id -> turn text`` from golden snapshot JSON files.

    Only per-turn player actions and narration are retained. Witness-panel
    scoring, reliability counters, durations, model metadata, and full
    ``turn_outputs`` payloads are intentionally ignored so this helper checks
    narration drift without replacing semantic/witness-panel evaluation.
    """
    index: ScenarioIndex = {}
    if not root.exists():
        return index
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        scenario_id = payload.get("scenario_id") or path.stem
        raw_turns = payload.get("turns", payload.get("captured_turns", []))
        index[str(scenario_id)] = [
            TurnText(
                index=int(raw.get("index", 0)),
                player_action=str(raw.get("player_action", "")),
                narration=str(raw.get("narration", "")),
            )
            for raw in raw_turns
        ]
    return index


def compare_narration_indexes(golden: ScenarioIndex, current: ScenarioIndex) -> list[str]:
    """Return actionable mismatch messages for current output vs golden snapshots."""
    failures: list[str] = []
    for scenario_id in sorted(golden.keys() - current.keys()):
        failures.append("{0} is missing from current output".format(scenario_id))
    for scenario_id in sorted(current.keys() - golden.keys()):
        failures.append("{0} is not present in golden snapshots".format(scenario_id))
    for scenario_id in sorted(golden.keys() & current.keys()):
        golden_turns = {turn.index: turn for turn in golden[scenario_id]}
        current_turns = {turn.index: turn for turn in current[scenario_id]}
        for index in sorted(golden_turns.keys() - current_turns.keys()):
            failures.append("{0} turn {1} is missing from current output".format(scenario_id, index))
        for index in sorted(current_turns.keys() - golden_turns.keys()):
            failures.append("{0} turn {1} is not present in golden snapshot".format(scenario_id, index))
        for index in sorted(golden_turns.keys() & current_turns.keys()):
            failures.extend(_compare_turn(scenario_id, index, golden_turns[index], current_turns[index]))
    return failures


def _compare_turn(scenario_id: str, index: int, golden: TurnText, current: TurnText) -> list[str]:
    failures: list[str] = []
    label = "{0} turn {1}".format(scenario_id, index)
    if golden.player_action != current.player_action:
        failures.append(
            "{0} player_action differs: golden={1!r} current={2!r}".format(
                label,
                golden.player_action,
                current.player_action,
            )
        )
    if golden.narration != current.narration:
        failures.append(
            "{0} narration differs:\n{1}".format(
                label,
                "\n".join(
                    unified_diff(
                        golden.narration.splitlines(),
                        current.narration.splitlines(),
                        fromfile="golden",
                        tofile="current",
                        lineterm="",
                    )
                ),
            )
        )
    return failures
