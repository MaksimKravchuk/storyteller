"""Read / write golden narration snapshots under ``benchmarks/golden/``.

Golden narration snapshots are git-tracked byte-exact references for benchmark
scenario narration. They intentionally exclude volatile run metadata such as
wall-clock timestamps, durations, judge panel output, and scores.

Read / compare helpers live in :mod:`benchmarks.harness._golden_read` so this
module stays within the project's WPS202 module-member budget.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from benchmarks.harness._archive_naming import sanitise_filename

if TYPE_CHECKING:
    from benchmarks.harness.types._captures import CapturedTurn
    from benchmarks.harness.types._scenarios import Scenario

_GOLDEN_DIR_NAME = "golden"
_ENCODING = "utf-8"
_SCHEMA_VERSION = 1


def golden_dir() -> Path:
    """Return the golden snapshot directory, creating it on first access."""
    package_root = Path(__file__).resolve().parent.parent
    archive_path = package_root / _GOLDEN_DIR_NAME
    archive_path.mkdir(parents=True, exist_ok=True)
    return archive_path


def golden_path(scenario_id: str) -> Path:
    """Return the canonical file path for a scenario's golden narration."""
    return golden_dir() / "{0}.json".format(sanitise_filename(scenario_id))


def _turn_to_dict(turn: CapturedTurn) -> dict[str, Any]:
    """Render a captured turn as stable JSON-safe narration evidence."""
    return {
        "index": turn.index,
        "narration": turn.narration,
        "player_action": turn.player_action,
        "turn_outputs": turn.turn_outputs.model_dump(mode="json"),
    }


def golden_payload(
    scenario: Scenario,
    captured_turns: Sequence[CapturedTurn],
    *,
    engine_git_sha: str,
    engine_models: Mapping[str, str],
) -> dict[str, Any]:
    """Build the canonical golden narration snapshot payload."""
    return {
        "engine_git_sha": engine_git_sha,
        "engine_models": dict(sorted(engine_models.items())),
        "scenario_id": scenario.id,
        "scenario_label": scenario.label,
        "schema_version": _SCHEMA_VERSION,
        "turns": [_turn_to_dict(turn) for turn in captured_turns],
    }


def write_golden_snapshot(
    scenario: Scenario,
    captured_turns: Sequence[CapturedTurn],
    *,
    engine_git_sha: str,
    engine_models: Mapping[str, str],
) -> Path:
    """Serialise a scenario's golden narration to ``benchmarks/golden/<scenario>.json``."""
    path = golden_path(scenario.id)
    path.write_text(
        json.dumps(
            golden_payload(
                scenario,
                captured_turns,
                engine_git_sha=engine_git_sha,
                engine_models=engine_models,
            ),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ),
        encoding=_ENCODING,
    )
    return path
