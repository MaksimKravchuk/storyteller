"""Implementation of the ``benchmarks golden-update`` subcommand.

``benchmarks golden-update <scenario>`` runs the benchmark scenario script just
far enough to capture narrator output, then writes the canonical golden
narration snapshot under ``benchmarks/golden/<scenario>.json``. The workflow can
hit paid provider APIs via the engine, so automated tests mock the runner rather
than executing live captures.
"""

from __future__ import annotations

import argparse
import sys

from benchmarks.harness.archive import current_git_sha
from benchmarks.harness.golden import write_golden_snapshot
from benchmarks.harness._run_execution import _run_script
from benchmarks.scenarios._registry import get_scenario
from config import Config, load_config


def _engine_model_summary(cfg: Config) -> dict[str, str]:
    """Capture the engine's per-role model ids for the reproducibility header."""
    return {
        "director_model": cfg.director_model,
        "agent_model": cfg.agent_model,
        "narrator_model": cfg.narrator_model,
        "dramaturge_model": cfg.dramaturge_model,
        "dramaturge_enabled": str(cfg.dramaturge_enabled).lower(),
    }


def _unknown_scenario(exc: KeyError) -> int:
    """Render registry validation failures as CLI usage errors."""
    message = exc.args[0] if exc.args else str(exc)
    sys.stderr.write("{0}\n".format(message))
    return 2


async def golden_update_command(args: argparse.Namespace) -> int:
    """Execute the ``golden-update`` subcommand."""
    try:
        scenario = get_scenario(args.scenario_id)
    except KeyError as exc:
        return _unknown_scenario(exc)
    cfg = load_config()
    captured_turns, _ = await _run_script(scenario, cfg)
    path = write_golden_snapshot(
        scenario,
        captured_turns,
        engine_git_sha=current_git_sha(),
        engine_models=_engine_model_summary(cfg),
    )
    sys.stdout.write("Golden updated {0} → {1}\n".format(scenario.id, path))
    sys.stdout.write("Open a PR titled `baseline: {0}` after reviewing the narration diff.\n".format(scenario.id))
    return 0
