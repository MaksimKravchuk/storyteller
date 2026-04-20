"""Row + header formatting helpers for the ``benchmarks compare`` subcommand."""

from __future__ import annotations

from benchmarks.cli._compare_classify import (
    PassRatePair,
    classify_pass_rate,
    classify_range,
)

_LABEL_COL_WIDTH = 40
_KEY_MEAN = "mean_awarded"
_KEY_MIN = "min_awarded"
_KEY_MAX = "max_awarded"


def format_header(tag: str, aggregate: dict) -> str:
    """Format the baseline/current header line."""
    return "{0}: {1} iter={2}  mean={3:.2f}/{4}  range=[{5}, {6}]".format(
        tag,
        aggregate["scenario_id"],
        aggregate["iterations"],
        aggregate[_KEY_MEAN],
        aggregate["total_base"],
        aggregate[_KEY_MIN],
        aggregate[_KEY_MAX],
    )


def format_scenario_classification(baseline: dict, current: dict) -> str:
    """Render the scenario-level classification banner."""
    verdict = classify_range(
        baseline[_KEY_MIN],
        baseline[_KEY_MAX],
        current[_KEY_MIN],
        current[_KEY_MAX],
    )
    return "Scenario verdict: {0}  (baseline={1:.2f} → current={2:.2f})".format(
        verdict,
        baseline[_KEY_MEAN],
        current[_KEY_MEAN],
    )


def _as_pair(baseline_rate: dict, current_rate: dict) -> PassRatePair:
    """Build the pass-rate pair from baseline + current element dicts."""
    return PassRatePair(
        label=current_rate["label"][:_LABEL_COL_WIDTH],
        baseline_passes=baseline_rate.get("passes", 0),
        baseline_iters=baseline_rate.get("iterations", 0),
        current_passes=current_rate["passes"],
        current_iters=current_rate["iterations"],
    )


def format_element_row(baseline_rate: dict, current_rate: dict) -> str:
    """Format one per-element pass-rate delta row."""
    pair = _as_pair(baseline_rate, current_rate)
    transition = "{0}/{1} → {2}/{3}".format(
        pair.baseline_passes,
        pair.baseline_iters,
        pair.current_passes,
        pair.current_iters,
    )
    return "{label:<40} {transition:>16} {marker:>12}".format(
        label=pair.label,
        transition=transition,
        marker=classify_pass_rate(pair),
    )


def format_table_header() -> str:
    """Format the per-element table header."""
    return "\n{0:<40} {1:>16} {2:>12}".format("element", "pass (base→cur)", "verdict")
