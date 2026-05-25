"""Pytest fixtures for the single-agent rubric tests.

Builds the witness panel once per session. ``RUBRIC_DEV_JUDGES`` (a
comma-separated list of roster aliases / model ids — e.g.
``haiku,gpt-5.4-nano``) overrides the default 6-model roster so
contributors can iterate cheaply without billing $5-10 per pytest
invocation. When the resolved panel falls below the signal floor
(:data:`MIN_PANEL_FOR_SIGNAL` in ``_rubric.py``) the ``panel``
fixture skips the requesting test — a 1-2 judge panel produces
degenerate majority votes that look like signal but aren't.
"""

from __future__ import annotations

import os

import pytest

from benchmarks.harness.panel import PanelAssembly, assemble_panel
from benchmarks.harness.types._scores import PanelMember, SkippedCandidate
from config import Config, load_config
from tests.rubric._rubric import MIN_PANEL_FOR_SIGNAL

_DEV_JUDGES_ENV = "RUBRIC_DEV_JUDGES"


def _format_skipped(skipped: list[SkippedCandidate]) -> str:
    """Render the skipped-candidate list for a pytest.skip message."""
    if not skipped:
        return "(none)"
    return ", ".join("{0} ({1})".format(skip.alias, skip.reason) for skip in skipped)


def _resolve_panel_overrides() -> list[str] | None:
    """Return the panel overrides from ``RUBRIC_DEV_JUDGES``, or None."""
    raw = os.environ.get(_DEV_JUDGES_ENV, "").strip()
    if not raw:
        return None
    return [token.strip() for token in raw.split(",") if token.strip()]


@pytest.fixture(scope="session")
def cfg() -> Config:
    """The :class:`Config` shared across the rubric session."""
    return load_config()


@pytest.fixture(scope="session")
def panel_assembly(cfg: Config) -> PanelAssembly:
    """Build the witness panel once per session.

    Honours ``RUBRIC_DEV_JUDGES`` so a developer can collapse the
    panel to two cheap judges for fast iteration without paying for
    the full 6-model roster on every test run.
    """
    return assemble_panel(cfg, overrides=_resolve_panel_overrides())


@pytest.fixture(scope="session")
def panel(panel_assembly: PanelAssembly) -> list[PanelMember]:
    """The list of panel members the rubric helpers consume.

    Skips the requesting test when the panel is too thin to produce
    meaningful majority votes — the alternative is fragile pass/fail
    signals that depend on a single judge.
    """
    members = panel_assembly.members
    if len(members) < MIN_PANEL_FOR_SIGNAL:
        pytest.skip(
            "Rubric panel has {0} members (below floor {1}); skipped: {2}".format(
                len(members),
                MIN_PANEL_FOR_SIGNAL,
                _format_skipped(panel_assembly.skipped),
            ),
        )
    return members
