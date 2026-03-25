"""Factory function to create a GameEngine from Config."""

from __future__ import annotations

from config import Config, resolve_model_config
from engine.game_engine import GameEngine


def create_engine(cfg: Config, language: str = "English") -> GameEngine:
    """Build a GameEngine from application config."""
    director_model = resolve_model_config(cfg.director_model, cfg)
    agent_model = resolve_model_config(cfg.agent_model, cfg)
    narrator_model = resolve_model_config(cfg.narrator_model, cfg)

    api_keys = {
        "openai": cfg.openai_api_key,
        "anthropic": cfg.anthropic_api_key,
    }

    return GameEngine(
        director_model=director_model,
        agent_model=agent_model,
        narrator_model=narrator_model,
        api_keys=api_keys,
        language=language,
    )
