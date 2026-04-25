"""Filesystem gathering: locate aggregate / iter JSONs by (set, scenario)."""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.model_sets import _patterns, _score

_BASELINE_LABEL = "baseline"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _engine_models_seed(iter_paths: list[Path]) -> dict[str, str]:
    if not iter_paths:
        return {}
    return _load(iter_paths[0]).get("engine_models", {})


def _baseline_score(results_dir: Path, scenario_id: str) -> _score.SetScore | None:
    matches = [path for path in results_dir.iterdir() if _patterns.is_baseline_aggregate(path.name, scenario_id)]
    if not matches:
        return None
    latest = max(matches, key=lambda path: path.name)
    return _score.from_aggregate(_load(latest), engine_models={})


def _set_score(results_dir: Path, set_name: str, scenario_id: str) -> _score.SetScore | None:
    aggregate_path: Path | None = None
    iter_paths: list[Path] = []
    for path in results_dir.iterdir():
        if _patterns.is_set_aggregate(path.name, set_name, scenario_id):
            aggregate_path = path
        elif _patterns.is_set_iter(path.name, set_name, scenario_id):
            iter_paths.append(path)
    iter_paths.sort()
    if aggregate_path is not None:
        models = _engine_models_seed(iter_paths)
        return _score.from_aggregate(_load(aggregate_path), engine_models=models)
    if iter_paths:
        payloads = [_load(iter_path) for iter_path in iter_paths]
        return _score.from_iters(payloads)
    return None


def gather(results_dir: Path, set_name: str, scenario_id: str) -> _score.SetScore | None:
    """Return the score for one (set, scenario) pair, or ``None`` if absent."""
    if set_name == _BASELINE_LABEL:
        return _baseline_score(results_dir, scenario_id)
    return _set_score(results_dir, set_name, scenario_id)
