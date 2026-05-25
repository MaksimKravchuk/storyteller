"""Diff-driven e2e test selector.

Reads ``git diff --name-only $BASE...HEAD`` and prints a space-separated
list of e2e test file paths to stdout — one per agent whose code paths
were touched. Empty stdout means no agent-relevant files changed and CI
can skip the e2e step entirely.

The ``PYTEST_AGENT_TESTS`` environment variable overrides the diff:

- ``all``        → every e2e test file
- ``none``       → no test files (empty stdout)
- ``a,b,c``      → only those agent keys
- unset / empty  → diff-driven via :func:`select_agents`

Invoke as ``python tests/e2e/_select_agents.py --base origin/main``.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Make the package importable when this script is invoked directly from
# the repo root (e.g. by a CI shell step).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.e2e._agent_matrix import (  # noqa: E402  (import after sys.path tweak)
    AGENT_TO_TEST_FILE,
    ALL_AGENTS,
    select_agents,
    selected_test_files,
)


def _changed_paths(base: str) -> list[str]:
    """Return the file paths in ``git diff --name-only $base...HEAD``."""
    output = subprocess.check_output(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        text=True,
    )
    return [line.strip() for line in output.splitlines() if line.strip()]


def _parse_csv_override(override: str) -> set[str]:
    """Return the agent keys in a comma-separated override, dropping unknowns."""
    tokens = (token.strip() for token in override.split(","))
    return {token for token in tokens if token in AGENT_TO_TEST_FILE}


def _resolve_agents(override: str, base: str) -> set[str]:
    """Map the override + git base into the agent key set to test."""
    normalised = override.strip().lower()
    if normalised == "all":
        return set(ALL_AGENTS)
    if normalised == "none":
        return set()
    if normalised:
        return _parse_csv_override(normalised)
    return select_agents(_changed_paths(base))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default="origin/main",
        help="git ref to diff against (default: origin/main)",
    )
    args = parser.parse_args()

    override = os.environ.get("PYTEST_AGENT_TESTS", "")
    agents = _resolve_agents(override, args.base)
    line = " ".join(selected_test_files(agents))
    sys.stdout.write(f"{line}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
