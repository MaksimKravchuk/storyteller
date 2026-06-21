"""Shared: build a Bayesian ``ScenarioVerdict`` from a current aggregate + pin.

Both ``bayes-report`` and ``pr-comment`` map a current aggregate dict to its
graded verdict against the pinned baseline; keeping that mapping in one place
stops the two callers from drifting.
"""

from __future__ import annotations

from benchmarks.harness import baselines
from benchmarks.harness._baselines_codec import aggregate_to_dict
from benchmarks.harness.bayes._report import verdict_for_scenario
from benchmarks.harness.bayes._types import ScenarioVerdict


def bayes_verdict_for(current: dict, rope: float) -> ScenarioVerdict | None:
    """Graded Bayesian verdict against the pinned baseline, or None when unpinned."""
    baseline = baselines.read_baseline(current["scenario_id"])
    if baseline is None:
        return None
    return verdict_for_scenario(
        aggregate_to_dict(baseline.aggregate),
        current,
        noise_floor_stdev=baseline.noise_floor_stdev,
        rope=rope,
    )
