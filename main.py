"""Storyteller — AI-powered text quest engine.

Simple CLI entry-point for testing the engine.
"""

import asyncio

from config import load_config
from engine.factory import create_engine


async def main() -> None:
    cfg = load_config()
    engine = create_engine(cfg)

    print("=" * 60)
    print("  STORYTELLER — AI Text Quest Engine")
    print("=" * 60)
    print(f"  Director: {cfg.director_model}")
    print(f"  Agents:   {cfg.agent_model}")
    print(f"  Narrator: {cfg.narrator_model}")
    print("=" * 60)
    print()

    setting = input("Describe your desired setting (e.g. 'Rome, 1st century AD'): ")
    print("\nResearching setting and generating opening scene...\n")

    opening = await engine.start_game(setting)
    print(opening)

    while True:
        print()
        action = input("> ").strip()
        if not action:
            continue
        if action.lower() in ("quit", "exit", "q"):
            print("Thanks for playing!")
            break

        response = await engine.process_action(action)
        print()
        print(response)


if __name__ == "__main__":
    asyncio.run(main())
