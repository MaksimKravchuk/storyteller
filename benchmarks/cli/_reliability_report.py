"""Implementation of the ``benchmarks reliability-report`` subcommand.

Walks per-iteration ``benchmarks/results/*.json`` archives, sums the
``reliability_counts`` blobs by ``(agent, event_type)``, and prints a
table. Aggregate ``*_aggregate.json`` files are skipped — they don't
carry the per-iteration counter shape.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from benchmarks.cli._reliability_table import format_table

_AGGREGATE_SUFFIX = "_aggregate.json"
_AGGREGATE_KEY = "element_pass_rates"
_PATH_NOT_FOUND_EXIT_CODE = 2

_CounterKey = tuple[str, str]
_CounterMap = dict[_CounterKey, int]
_PayloadCell = tuple[_CounterKey, int]


def _iter_iteration_files(root: Path) -> Iterable[Path]:
    """Yield every per-iteration JSON archive under ``root``.

    Accepts either a single JSON file or a directory; in the directory
    case, ``*_aggregate.json`` siblings are excluded so the aggregate's
    different shape never reaches the per-iteration parser.
    """
    if root.is_file():
        yield root
        return
    for candidate in sorted(root.glob("*.json")):
        if candidate.name.endswith(_AGGREGATE_SUFFIX):
            continue
        yield candidate


def _load_per_iteration_payload(path: Path) -> dict[str, Any] | None:
    """Return the JSON payload if it looks like a per-iteration archive.

    Aggregate archives carry ``element_pass_rates`` at top level — we
    skip those defensively so a mixed directory still tallies correctly.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or _AGGREGATE_KEY in raw:
        return None
    return raw


def _iter_payload_cells(payload: dict[str, Any]) -> Iterable[_PayloadCell]:
    """Yield one ``((agent, event_type), count)`` cell per blob entry."""
    blob = payload.get("reliability_counts") or {}
    for agent, by_event in blob.items():
        if not isinstance(by_event, dict):
            continue
        for event_type, count in by_event.items():
            yield (agent, event_type), int(count)


def _accumulate(counters: _CounterMap, payload: dict[str, Any]) -> None:
    """Fold one iteration's ``reliability_counts`` blob into ``counters``."""
    for key, count in _iter_payload_cells(payload):
        counters[key] = counters.get(key, 0) + count


def aggregate_counts(root: Path) -> _CounterMap:
    """Walk ``root`` and return summed ``(agent, event_type) -> count`` counters."""
    counters: _CounterMap = {}
    for candidate in _iter_iteration_files(root):
        payload = _load_per_iteration_payload(candidate)
        if payload is not None:
            _accumulate(counters, payload)
    return counters


def reliability_report_command(args: argparse.Namespace) -> int:
    """Execute the ``reliability-report`` subcommand."""
    target = Path(args.path)
    if not target.exists():
        sys.stderr.write("Path not found: {0}\n".format(target))
        return _PATH_NOT_FOUND_EXIT_CODE
    counters = aggregate_counts(target)
    sys.stdout.write("{0}\n".format(format_table(counters)))
    return 0
