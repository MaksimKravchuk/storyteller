"""Implementation of the ``benchmarks pin`` subcommand.

``benchmarks pin <scenario_id> --from <aggregate.json>`` copies the aggregate's
contents into ``benchmarks/baselines/<scenario_id>.json`` and stamps the
metadata header (``baselined_at``, ``engine_git_sha``, ``engine_models``,
``iterations``, ``noise_floor_stdev``).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from benchmarks.cli._calibrate_io import read_calibration_for
from benchmarks.harness import baselines
from benchmarks.harness.types._aggregates import ElementPassRate, PinnedBaseline, ScenarioAggregate


def _load_aggregate_payload(path_str: str) -> dict:
    """Read a single aggregate JSON file, raising a friendly error on miss."""
    path = Path(path_str)
    if not path.is_file():
        raise FileNotFoundError("Aggregate not found: {0}".format(path_str))
    return json.loads(path.read_text(encoding="utf-8"))


def _aggregate_from_payload(payload: dict) -> ScenarioAggregate:
    """Rebuild a :class:`ScenarioAggregate` from an aggregate-archive JSON payload."""
    return ScenarioAggregate(
        scenario_id=payload["scenario_id"],
        scenario_label=payload["scenario_label"],
        iterations=payload["iterations"],
        total_base=payload["total_base"],
        mean_awarded=payload["mean_awarded"],
        min_awarded=payload["min_awarded"],
        max_awarded=payload["max_awarded"],
        element_pass_rates=[
            ElementPassRate(
                element_id=rate["element_id"],
                label=rate["label"],
                base_value=rate["base_value"],
                passes=rate["passes"],
                iterations=rate["iterations"],
            )
            for rate in payload.get("element_pass_rates", [])
        ],
        iteration_totals=list(payload.get("iteration_totals", [])),
        stdev_awarded=payload.get("stdev_awarded", float(0)),
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_noise_floor(scenario_id: str, fallback: float) -> float:
    """Prefer the calibration file's stdev for ``scenario_id``; else use ``fallback``."""
    calibrated = read_calibration_for(scenario_id)
    if calibrated is None:
        return fallback
    return calibrated.stdev


def pin_command(args: argparse.Namespace) -> int:
    """Execute the ``pin`` subcommand."""
    payload = _load_aggregate_payload(args.from_path)
    if payload.get("scenario_id") != args.scenario_id:
        raise ValueError(
            "Aggregate scenario_id {0!r} does not match target {1!r}".format(
                payload.get("scenario_id"),
                args.scenario_id,
            ),
        )
    aggregate = _aggregate_from_payload(payload)
    baseline = PinnedBaseline(
        aggregate=aggregate,
        baselined_at=_now_iso(),
        engine_git_sha=payload.get("engine_git_sha", ""),
        engine_models=dict(payload.get("engine_models", {})),
        iterations=aggregate.iterations,
        noise_floor_stdev=_resolve_noise_floor(args.scenario_id, aggregate.stdev_awarded),
    )
    path = baselines.write_baseline(baseline)
    sys.stdout.write("Pinned {0} → {1}\n".format(args.scenario_id, path))
    return 0
