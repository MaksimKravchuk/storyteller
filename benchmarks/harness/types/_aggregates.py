"""Cross-iteration aggregates over :class:`ScenarioReport`."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ElementPassRate:
    """Per-element pass rate across N iterations of one scenario.

    ``k_yes`` / ``n_votes`` carry the summed judge tally for evidence-LLM
    elements (0 for deterministic ones). They give the Bayesian layer
    judge-level resolution — a wider panel tightens the per-element posterior
    without another engine iteration — while ``passes`` / ``iterations`` remain
    the coarse fallback for baselines pinned before tallies were retained.
    """

    element_id: str
    label: str
    base_value: int
    passes: int
    iterations: int
    k_yes: int = 0
    n_votes: int = 0


@dataclass(frozen=True)
class ScenarioAggregate:
    """Mean + [min, max] totals and per-element pass rates over N iterations."""

    scenario_id: str
    scenario_label: str
    iterations: int
    total_base: int
    mean_awarded: float
    min_awarded: int
    max_awarded: int
    element_pass_rates: list[ElementPassRate]
    iteration_totals: list[int]
    stdev_awarded: float


@dataclass(frozen=True)
class PinnedBaseline:
    """Pinned per-scenario baseline plus reproducibility metadata.

    ``aggregate`` is the canonical aggregate the new run is compared against.
    ``noise_floor_stdev`` is the calibrated stdev used by the ratchet predicate;
    it is intentionally separate from ``aggregate.stdev_awarded`` (which is the
    current run's descriptive stdev) — see ADR-0002.
    """

    aggregate: ScenarioAggregate
    baselined_at: str
    engine_git_sha: str
    engine_models: dict[str, str]
    iterations: int
    noise_floor_stdev: float
