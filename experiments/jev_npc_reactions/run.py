"""Compare the NPC aggression gate, Jev, and the existing Actor."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from cast.dice import AGGRESSION_THRESHOLDS
from experiments.jev_npc_reactions import actor_eval, jev_eval
from experiments.jev_npc_reactions.case_data import Case, jev_state, load_cases

_D20_SIDES = 20
_DEFAULT_OUTPUT_NAME = "storyteller_jev_results.json"


def _baseline(case: Case) -> dict[str, Any]:
    threshold = AGGRESSION_THRESHOLDS.get(case.mood)
    probability = 0 if threshold is None else (_D20_SIDES + 1 - threshold) / _D20_SIDES
    return {
        "case": case.name,
        "language": case.language,
        "mood": case.mood,
        "dice_attack_probability": probability,
        "state": jev_state(case),
    }


async def _live_case(case: Case, jev_key: str, actor_key: str) -> dict[str, Any]:
    jev, actor = await asyncio.gather(
        asyncio.to_thread(jev_eval.call_jev, case, jev_key),
        actor_eval.call_actor(case, actor_key),
    )
    return {**_baseline(case), "jev": jev, "actor": actor}


async def run(live: bool) -> list[dict[str, Any]]:
    """Run all fixed cases, with optional paid provider calls."""
    cases = load_cases()
    if not live:
        return [_baseline(case) for case in cases]
    jev_key = os.environ.get("TYPESAFE_API_KEY", "")
    actor_key = os.environ.get("OPENAI_API_KEY", "")
    if not jev_key or not actor_key:
        sys.exit("Live mode requires TYPESAFE_API_KEY and OPENAI_API_KEY")
    tasks = (_live_case(case, jev_key, actor_key) for case in cases)
    return list(await asyncio.gather(*tasks))


def main() -> None:
    """Run the exploratory comparison and save raw output locally."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    default_output = Path(tempfile.gettempdir()) / _DEFAULT_OUTPUT_NAME
    parser.add_argument("--output", type=Path, default=default_output)
    args = parser.parse_args()
    rows = asyncio.run(run(args.live))
    args.output.write_text(f"{json.dumps(rows, ensure_ascii=False, indent=2)}\n")
    message = "Wrote {0} cases to {1}; live={2}\n".format(len(rows), args.output, args.live)
    sys.stdout.write(message)


if __name__ == "__main__":
    main()
