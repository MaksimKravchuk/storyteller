"""Cross-set comparison report — entry point.

Walks ``benchmarks/results/`` and renders one markdown table per scenario
that puts baseline / max / optimal / economy side-by-side. Reads aggregate
JSON files where they exist and falls back to per-iteration JSONs (so
partial-success scenarios still appear, with the iteration count visible).
"""

from __future__ import annotations

import sys
from pathlib import Path

from benchmarks.model_sets._render import Comparison, render

_RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
_REPORT_PATH = Path(__file__).resolve().parent / "comparison.md"

_COMPARISON = Comparison(
    sets=("baseline", "max", "optimal", "economy"),
    scenarios=(
        "memory_follow_up_marcus",
        "memory_follow_up_marcus_graph_only",
        "autonomy_three_guards_tavern",
        "escalation_guard_assault",
        "npc_autonomy_murder_plot",
    ),
    results_dir=_RESULTS_DIR,
)


def main() -> int:
    body = render(_COMPARISON)
    _REPORT_PATH.write_text(body, encoding="utf-8")
    sys.stdout.write(body)
    sys.stdout.write("\n\nReport written to: {0}\n".format(_REPORT_PATH))
    return 0


if __name__ == "__main__":
    sys.exit(main())
