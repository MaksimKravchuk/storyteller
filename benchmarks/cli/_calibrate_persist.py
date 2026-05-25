"""Persist calibration outcomes to JSON + emit user-facing warnings.

Split out of :mod:`benchmarks.cli._calibrate` so the runner module stays small.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from benchmarks.cli._calibrate_io import CalibrationEntry, write_calibration
from benchmarks.harness.types._aggregates import ScenarioAggregate

_HIGH_NOISE_RATIO = 0.15
_HIGH_NOISE_RECOMMENDATION = 10
_WARNING_LINE = (
    "warning: scenario {0!r} has high noise (stdev={1:.2f} > 0.15 * total_base={2}); "
    "recommend recalibrating with --iterations {3}\n"
)


@dataclass(frozen=True)
class CalibrationResult:
    """One scenario's calibration outcome: aggregate + engine pins."""

    scenario_id: str
    aggregate: ScenarioAggregate
    engine_git_sha: str
    engine_models: dict[str, str]


def _entries_for(calibration_results: list[CalibrationResult]) -> dict[str, CalibrationEntry]:
    """Adapt :class:`CalibrationResult` records into :class:`CalibrationEntry` rows."""
    return {
        record.scenario_id: CalibrationEntry(
            mean=record.aggregate.mean_awarded,
            stdev=record.aggregate.stdev_awarded,
            iterations=record.aggregate.iterations,
            engine_git_sha=record.engine_git_sha,
            models=dict(record.engine_models),
        )
        for record in calibration_results
    }


def _is_high_noise(aggregate: ScenarioAggregate) -> bool:
    """Return ``True`` when stdev exceeds 15% of the scenario's total base."""
    if aggregate.total_base <= 0:
        return False
    return aggregate.stdev_awarded > _HIGH_NOISE_RATIO * aggregate.total_base


def _emit_high_noise_warnings(calibration_results: list[CalibrationResult]) -> None:
    """Print one warning per scenario whose stdev exceeds the high-noise threshold."""
    for record in calibration_results:
        if not _is_high_noise(record.aggregate):
            continue
        sys.stdout.write(
            _WARNING_LINE.format(
                record.scenario_id,
                record.aggregate.stdev_awarded,
                record.aggregate.total_base,
                _HIGH_NOISE_RECOMMENDATION,
            ),
        )


def persist_calibration(calibration_results: list[CalibrationResult]) -> None:
    """Write the calibration JSON + emit user-facing warnings."""
    path = write_calibration(_entries_for(calibration_results))
    sys.stdout.write("Wrote calibration to {0}\n".format(path))
    _emit_high_noise_warnings(calibration_results)
