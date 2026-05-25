"""Read/write helpers for ``benchmarks/baselines/.calibration.json``.

Pulled out of :mod:`benchmarks.cli._calibrate` so the ``pin`` subcommand can
read calibration data without importing the runner-heavy ``_calibrate`` module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from benchmarks.harness import baselines

_CALIBRATION_FILENAME = ".calibration.json"
_ENCODING = "utf-8"


@dataclass(frozen=True)
class CalibrationEntry:
    """Per-scenario calibration record: mean, stdev, iterations, engine pins."""

    mean: float
    stdev: float
    iterations: int
    engine_git_sha: str
    models: dict[str, str]


def calibration_path() -> Path:
    """Return the canonical calibration JSON path under ``benchmarks/baselines/``."""
    return baselines.baselines_dir() / _CALIBRATION_FILENAME


def write_calibration(entries: dict[str, CalibrationEntry]) -> Path:
    """Serialise ``entries`` to the calibration JSON, returning its path."""
    payload = {
        scenario_id: {
            "mean": entry.mean,
            "stdev": entry.stdev,
            "iterations": entry.iterations,
            "engine_git_sha": entry.engine_git_sha,
            "models": dict(entry.models),
        }
        for scenario_id, entry in entries.items()
    }
    path = calibration_path()
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding=_ENCODING,
    )
    return path


def read_calibration() -> dict[str, CalibrationEntry]:
    """Read the calibration JSON; return ``{}`` when absent."""
    path = calibration_path()
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding=_ENCODING))
    return {
        scenario_id: CalibrationEntry(
            mean=entry["mean"],
            stdev=entry["stdev"],
            iterations=entry["iterations"],
            engine_git_sha=entry.get("engine_git_sha", ""),
            models=dict(entry.get("models", {})),
        )
        for scenario_id, entry in payload.items()
    }


def read_calibration_for(scenario_id: str) -> CalibrationEntry | None:
    """Return the calibration entry for one scenario, or ``None`` when absent."""
    return read_calibration().get(scenario_id)
