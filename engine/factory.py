"""Factory functions to create a GameEngine from Config."""

from __future__ import annotations

from typing import TYPE_CHECKING

from config import Config, resolve_model_config
from engine.game_engine import GameEngine

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph
    from models.game_state import GameState
    from timeline.event import GameEvent


def create_engine(cfg: Config, language: str = "English") -> GameEngine:
    """Build a GameEngine from application config."""
    return _build_engine(cfg, language)


async def create_engine_from_state(
    cfg: Config,
    game_state: GameState,
    knowledge_graph: KnowledgeGraph,
    events: list[GameEvent],
    language: str = "English",
) -> GameEngine:
    """Build a GameEngine and restore it from previously saved state."""
    engine = _build_engine(cfg, language)
    await engine.restore_session(game_state, knowledge_graph, events)
    return engine


def _build_engine(cfg: Config, language: str) -> GameEngine:
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
