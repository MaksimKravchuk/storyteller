"""Filename patterns for benchmark archive files."""

from __future__ import annotations

import re

_SET_AGG_RE = re.compile(
    r"^set-(?P<set>[^_]+)__\d{4}-\d{2}-\d{2}T[\d-]+_[0-9a-f]+_(?P<sid>.+)_aggregate\.json$",
)
_SET_ITER_RE = re.compile(
    r"^set-(?P<set>[^_]+)__\d{4}-\d{2}-\d{2}T[\d-]+_[0-9a-f]+_(?P<sid>.+)_iter(?P<iter>\d+)\.json$",
)
_BASE_AGG_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T[\d-]+_[0-9a-f]+_(?P<sid>.+)_aggregate\.json$",
)


def _matches_set(match: re.Match[str] | None, set_name: str, scenario_id: str) -> bool:
    if match is None:
        return False
    if match.group("set") != set_name:
        return False
    return match.group("sid") == scenario_id


def is_baseline_aggregate(name: str, scenario_id: str) -> bool:
    """True if ``name`` is an untagged (baseline) aggregate file for ``scenario_id``."""
    match = _BASE_AGG_RE.match(name)
    return match is not None and match.group("sid") == scenario_id


def is_set_aggregate(name: str, set_name: str, scenario_id: str) -> bool:
    """True if ``name`` is the per-set aggregate file for (set, scenario)."""
    return _matches_set(_SET_AGG_RE.match(name), set_name, scenario_id)


def is_set_iter(name: str, set_name: str, scenario_id: str) -> bool:
    """True if ``name`` is a per-iteration file for (set, scenario)."""
    return _matches_set(_SET_ITER_RE.match(name), set_name, scenario_id)
