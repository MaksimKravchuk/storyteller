"""Read / write pinned :class:`PinnedBaseline` JSON under ``benchmarks/baselines/``.

Baselines are git-tracked so the canonical "current main" reference travels with
the repo. Each scenario has at most one baseline file at
``benchmarks/baselines/<scenario_id>.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.harness._archive_naming import sanitise_filename
from benchmarks.harness._baselines_codec import aggregate_from_dict, aggregate_to_dict
from benchmarks.harness.types._aggregates import PinnedBaseline

_BASELINES_DIR_NAME = "baselines"
_ENCODING = "utf-8"
_KEY_ITERATIONS = "iterations"
_KEY_AGGREGATE = "aggregate"


def baselines_dir() -> Path:
    """Return the baselines directory, creating it on first access."""
    package_root = Path(__file__).resolve().parent.parent
    archive_path = package_root / _BASELINES_DIR_NAME
    archive_path.mkdir(parents=True, exist_ok=True)
    return archive_path


def baseline_path(scenario_id: str) -> Path:
    """Return the canonical file path for a scenario's pinned baseline."""
    return baselines_dir() / "{0}.json".format(sanitise_filename(scenario_id))


def write_baseline(baseline: PinnedBaseline) -> Path:
    """Serialise ``baseline`` to ``benchmarks/baselines/<scenario>.json``."""
    path = baseline_path(baseline.aggregate.scenario_id)
    payload = {
        "baselined_at": baseline.baselined_at,
        "engine_git_sha": baseline.engine_git_sha,
        "engine_models": dict(baseline.engine_models),
        _KEY_ITERATIONS: baseline.iterations,
        "noise_floor_stdev": baseline.noise_floor_stdev,
        _KEY_AGGREGATE: aggregate_to_dict(baseline.aggregate),
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding=_ENCODING,
    )
    return path


def read_baseline(scenario_id: str) -> PinnedBaseline | None:
    """Read a pinned baseline; return ``None`` when none has been pinned."""
    path = baseline_path(scenario_id)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding=_ENCODING))
    return PinnedBaseline(
        aggregate=aggregate_from_dict(payload[_KEY_AGGREGATE]),
        baselined_at=payload["baselined_at"],
        engine_git_sha=payload["engine_git_sha"],
        engine_models=dict(payload.get("engine_models", {})),
        iterations=payload[_KEY_ITERATIONS],
        noise_floor_stdev=payload["noise_floor_stdev"],
    )


def list_baselines() -> list[str]:
    """Return scenario ids that have a pinned baseline, sorted alphabetically."""
    return sorted(path.stem for path in baselines_dir().glob("*.json"))
