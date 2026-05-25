"""Reset + snapshot the per-scenario reliability counters for benchmark runs.

The engine itself resets counters at every turn boundary inside
``engine.session_ops``. Benchmark scenarios drive the engine directly
through ``create_engine_from_state`` and never touch the session-ops
turn boundary, so we reset once at the start of each scenario and
snapshot once at the end. The snapshot is flattened into
``{agent: {event_type: count}}`` so it round-trips cleanly through
``dataclasses.asdict`` into the per-iteration JSON archive.
"""

from __future__ import annotations

from cast import _reliability_metrics as reliability_metrics


def reset_for_scenario() -> None:
    """Initialise an empty counter map ahead of a scenario's first turn."""
    reliability_metrics.reset_counters()


def collect_reliability_counts() -> dict[str, dict[str, int]]:
    """Snapshot the counters into the JSON-safe nested-dict shape."""
    raw = reliability_metrics.snapshot_counters()
    out: dict[str, dict[str, int]] = {}
    for (agent, event_type), count in raw.items():
        out.setdefault(agent, {})[event_type] = count
    return out
