"""Factory functions to create a GameEngine from Config."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cast.narrative_test_agent import NarrativeTestAgent
from config import Config, get_api_key_for_provider, resolve_model_config
from engine.game_engine import GameEngine
from llm.factory import create_llm_client

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


def create_narrative_test_agent(cfg: Config) -> NarrativeTestAgent:
    """Build a :class:`NarrativeTestAgent` backed by the higher-tier reviewer model.

    The reviewer model is picked up from ``cfg.narrative_test_model`` and
    routed through the normal provider auto-detection, so Claude Sonnet
    and GPT-class reviewers are both supported without changing any code
    in the agent itself.
    """
    reviewer_model = resolve_model_config(cfg.narrative_test_model, cfg)
    api_key = get_api_key_for_provider(reviewer_model.provider, cfg)
    reviewer_client = create_llm_client(reviewer_model, api_key=api_key)
    return NarrativeTestAgent(llm_client=reviewer_client)


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
