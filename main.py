"""Storyteller — AI-powered text quest engine.

Simple CLI entry-point for testing the engine.
"""

import asyncio

from config import load_config, resolve_model_config
from engine.game_engine import GameEngine


async def main() -> None:
    # Load configuration from .env / environment variables
    cfg = load_config()

    # Build ModelConfig instances from env-configured model names
    director_model = resolve_model_config(cfg.director_model, cfg)
    agent_model = resolve_model_config(cfg.agent_model, cfg)
    narrator_model = resolve_model_config(cfg.narrator_model, cfg)

    # Collect API keys per provider
    api_keys = {
        "openai": cfg.openai_api_key,
        "anthropic": cfg.anthropic_api_key,
    }

    engine = GameEngine(
        director_model=director_model,
        agent_model=agent_model,
        narrator_model=narrator_model,
        api_keys=api_keys,
    )

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
