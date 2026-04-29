"""Job-list helpers shared by the ``run`` subcommand."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from benchmarks.harness.archive import current_git_sha
from benchmarks.harness.types._scenarios import Scenario
from benchmarks.scenarios._registry import ALL_SCENARIOS, get_scenario
from config import Config, load_config


@dataclass(frozen=True)
class RunContext:
    """Parameters shared across every iteration in one ``run`` invocation."""

    cfg: Config
    overrides: list[str] | None
    sha: str
    max_judges: int | None


def _parse_judge_overrides(raw: str | None) -> list[str] | None:
    """Split the ``--judges`` argument on commas, stripping whitespace."""
    if not raw:
        return None
    return [alias.strip() for alias in raw.split(",") if alias.strip()]


def _scenarios_for(args: argparse.Namespace) -> list[Scenario]:
    """Pick the scenarios to run from the ``--scenario`` flags."""
    if args.scenario:
        return [get_scenario(sid) for sid in args.scenario]
    return list(ALL_SCENARIOS)


def build_context(args: argparse.Namespace) -> RunContext:
    """Build the immutable context from parsed CLI arguments."""
    return RunContext(
        cfg=load_config(),
        overrides=_parse_judge_overrides(args.judges),
        sha=current_git_sha(),
        max_judges=args.max_judges,
    )


def expand_jobs(args: argparse.Namespace) -> list[tuple[Scenario, int]]:
    """Expand scenarios × iterations into a flat job list."""
    iterations = args.iterations
    return [(scenario, iteration) for scenario in _scenarios_for(args) for iteration in range(iterations)]
