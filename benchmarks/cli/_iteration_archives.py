"""Shared helpers for walking per-iteration result archives.

Both ``reliability-report`` and ``narration-diff`` consume per-iteration
``benchmarks/results/*.json`` archives and must skip the ``*_aggregate.json``
siblings, whose shape differs. This module owns that walk so the two
subcommands agree on what counts as a per-iteration archive.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

_AGGREGATE_SUFFIX = "_aggregate.json"
_AGGREGATE_KEY = "element_pass_rates"


def iter_iteration_files(root: Path) -> Iterable[Path]:
    """Yield every per-iteration JSON archive under ``root``.

    Accepts either a single JSON file or a directory; in the directory case,
    ``*_aggregate.json`` siblings are excluded so the aggregate's different
    shape never reaches the per-iteration parser.
    """
    if root.is_file():
        yield root
        return
    for candidate in sorted(root.glob("*.json")):
        if not candidate.name.endswith(_AGGREGATE_SUFFIX):
            yield candidate


def load_per_iteration_payload(path: Path) -> dict[str, Any] | None:
    """Return the JSON payload if it looks like a per-iteration archive.

    Aggregate archives carry ``element_pass_rates`` at top level — we skip
    those defensively so a mixed directory still parses correctly.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or _AGGREGATE_KEY in raw:
        return None
    return raw
