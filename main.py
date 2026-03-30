"""Storyteller — AI-powered text quest engine.

Simple CLI entry-point for testing the engine.
"""

from __future__ import annotations

import asyncio
import sys

from config import load_config
from engine.factory import create_engine

_SEPARATOR = "=" * 60
_QUIT_COMMANDS = frozenset(("quit", "exit", "q"))


async def main() -> None:
    cfg = load_config()
    engine = create_engine(cfg)

    sys.stdout.write(f"{_SEPARATOR}\n")
    sys.stdout.write("  STORYTELLER — AI Text Quest Engine\n")
    sys.stdout.write(f"{_SEPARATOR}\n")
    sys.stdout.write(f"  Director: {cfg.director_model}\n")
    sys.stdout.write(f"  Agents:   {cfg.agent_model}\n")
    sys.stdout.write(f"  Narrator: {cfg.narrator_model}\n")
    sys.stdout.write(f"{_SEPARATOR}\n\n")

    sys.stdout.write("Describe your desired setting (e.g. 'Rome, 1st century AD'): ")
    sys.stdout.flush()
    setting = sys.stdin.readline().strip()

    sys.stdout.write("\nResearching setting and generating opening scene...\n\n")
    opening = await engine.start_game(setting)
    sys.stdout.write(f"{opening}\n")

    while True:
        sys.stdout.write("\n> ")
        sys.stdout.flush()
        action = sys.stdin.readline().strip()
        if not action:
            continue
        if action.lower() in _QUIT_COMMANDS:
            sys.stdout.write("Thanks for playing!\n")
            break

        response = await engine.process_action(action)
        sys.stdout.write(f"\n{response}\n")


if __name__ == "__main__":
    asyncio.run(main())
