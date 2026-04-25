"""Markdown rendering for the cross-set comparison report."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from benchmarks.model_sets._format import format_iterations, format_models, format_score
from benchmarks.model_sets._gather import gather


@dataclass(frozen=True)
class Comparison:
    """Inputs for the rendering functions."""

    sets: tuple[str, ...]
    scenarios: tuple[str, ...]
    results_dir: Path


def _summary_table(comparison: Comparison) -> list[str]:
    header = " | ".join(comparison.sets)
    sep = " | ".join("---" for _ in comparison.sets)
    lines = [
        "## Summary (mean awarded / total base)",
        "",
        "| scenario | {0} |".format(header),
        "| --- | {0} |".format(sep),
    ]
    for sid in comparison.scenarios:
        cells = [format_score(gather(comparison.results_dir, name, sid)) for name in comparison.sets]
        lines.append("| `{0}` | {1} |".format(sid, " | ".join(cells)))
    lines.append("")
    return lines


def _scenario_block(scenario_id: str, comparison: Comparison) -> list[str]:
    lines = [
        "## `{0}`".format(scenario_id),
        "",
        "| set | mean / base | iterations | engine |",
        "| --- | --- | --- | --- |",
    ]
    for set_name in comparison.sets:
        score = gather(comparison.results_dir, set_name, scenario_id)
        cells = [set_name, format_score(score), format_iterations(score), format_models(score)]
        lines.append("| **{0}** | {1} | {2} | {3} |".format(*cells))
    lines.append("")
    return lines


def render(comparison: Comparison) -> str:
    """Render the full cross-set comparison report as a markdown string."""
    lines = ["# Model-set comparison", ""]
    lines.extend(_summary_table(comparison))
    for sid in comparison.scenarios:
        lines.extend(_scenario_block(sid, comparison))
    return "\n".join(lines)
