"""Shared loader: the latest current aggregate per scenario from a results dir."""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path


def latest_aggregates(results_dir: Path) -> list[dict]:
    """One aggregate dict per scenario_id — the last in sorted order wins.

    An archive directory can hold several aggregate files for the same scenario
    (multiple runs); deduplicating here keeps a portfolio posterior from
    double-counting history.
    """
    by_scenario: OrderedDict[str, dict] = OrderedDict()
    for path in sorted(results_dir.glob("*_aggregate.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        by_scenario[payload["scenario_id"]] = payload
    return list(by_scenario.values())
