"""Run matched dialogue comparisons: Actor, reminder, and Jev-assisted Actor."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from experiments.jev_dialogue_reactions.case_data import Case, load_cases
from experiments.jev_dialogue_reactions.jev_eval import call_jev
from experiments.jev_dialogue_reactions.providers import call_actor

_MAX_CONCURRENT_CALLS = 4
_DEFAULT_ITERATIONS = 3
_DEFAULT_OUTPUT_DIR = Path("/private/tmp/storyteller-jev-dialogue-results")


class _TrialRunner:
    def __init__(self, jev_key: str, actor_key: str) -> None:
        self._jev_key = jev_key
        self._actor_key = actor_key
        self._actor_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_CALLS)
        self._jev_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_CALLS)

    async def run(self, case: Case) -> dict[str, Any]:
        """Run matched Actor arms from fresh state with one Jev judgment."""
        baseline, reminder, jev = await asyncio.gather(
            self._actor(case, "baseline"),
            self._actor(case, "reminder"),
            self._jev(case),
        )
        guided = await self._actor(case, "jev", jev)
        return {
            "case": case.name,
            "jev": jev,
            "baseline": baseline,
            "reminder": reminder,
            "jev_guided": guided,
        }

    async def _actor(
        self,
        case: Case,
        variant: str,
        jev: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with self._actor_semaphore:
            return await call_actor(case, variant, self._actor_key, jev)

    async def _jev(self, case: Case) -> dict[str, Any]:
        async with self._jev_semaphore:
            return await asyncio.to_thread(call_jev, case, self._jev_key)


async def run_iteration(
    cases: tuple[Case, ...],
    jev_key: str,
    actor_key: str,
) -> list[dict[str, Any]]:
    """Run one independent repetition of every fixed case."""
    runner = _TrialRunner(jev_key, actor_key)
    tasks = [runner.run(case) for case in cases]
    return list(await asyncio.gather(*tasks))


def _write_output(output: Path, rows: list[dict[str, Any]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(rows, ensure_ascii=False, indent=2)
    output.write_text("{0}\n".format(payload), encoding="utf-8")
    sys.stdout.write("Wrote {0} cases to {1}\n".format(len(rows), output))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--iterations", type=int, default=_DEFAULT_ITERATIONS)
    parser.add_argument("--output-dir", type=Path, default=_DEFAULT_OUTPUT_DIR)
    return parser


def _run_live(args: argparse.Namespace, cases: tuple[Case, ...]) -> None:
    jev_key = os.environ.get("TYPESAFE_API_KEY", "")
    actor_key = os.environ.get("OPENAI_API_KEY", "")
    if not jev_key or not actor_key:
        sys.exit("Live mode requires TYPESAFE_API_KEY and OPENAI_API_KEY")
    if args.iterations < 1:
        sys.exit("Iterations must be positive")
    for iteration in range(args.iterations):
        output = args.output_dir / "results_iter{0}.json".format(iteration)
        _write_output(output, asyncio.run(run_iteration(cases, jev_key, actor_key)))


def main() -> None:
    """Execute dry-run or bounded live comparison without persisting credentials."""
    args = _build_parser().parse_args()
    cases = load_cases()
    if not args.live:
        sys.stdout.write("Prepared {0} fixed cases; no provider calls made.\n".format(len(cases)))
        return
    _run_live(args, cases)


if __name__ == "__main__":
    main()
