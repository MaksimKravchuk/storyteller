"""Filename-construction helpers for the results archive."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from benchmarks.harness.types._scores import ScenarioReport

_TIMESTAMP_FORMAT = "%Y-%m-%dT%H-%M-%S"
_SAFE_FILENAME_CHARS = frozenset("-.")


def _safe_char(char: str) -> str:
    """Return ``char`` unchanged when filesystem-safe; otherwise ``_``."""
    if char.isalnum() or char in _SAFE_FILENAME_CHARS:
        return char
    return "_"


def sanitise_filename(component: str) -> str:
    """Scrub filesystem-hostile characters from a filename component."""
    return "".join(_safe_char(char) for char in component)


def _parse_timestamp(started_at: str) -> str:
    """Format the archive timestamp, falling back to now on parse failure."""
    try:
        started = datetime.fromisoformat(started_at)
    except ValueError:
        started = datetime.now(timezone.utc)
    return started.strftime(_TIMESTAMP_FORMAT)


def current_timestamp() -> str:
    """Return ``now`` formatted to match the archive filename timestamp style."""
    return datetime.now(timezone.utc).strftime(_TIMESTAMP_FORMAT)


def sha_fragment(sha: str) -> str:
    """Return a filesystem-safe 7-char SHA prefix (or ``nosha`` when empty)."""
    return sanitise_filename(sha[:7]) or "nosha"


def file_stem(report: ScenarioReport) -> str:
    """Build the ``<timestamp>_<sha>_<scenario>_iterN`` stem."""
    return "{0}_{1}_{2}_iter{3}".format(
        _parse_timestamp(report.started_at),
        sha_fragment(report.engine_git_sha),
        sanitise_filename(report.scenario_id),
        report.iteration,
    )
