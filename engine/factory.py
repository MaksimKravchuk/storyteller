"""Factory functions to create a GameEngine from Config."""

from __future__ import annotations

from typing import TYPE_CHECKING

from config import Config, resolve_model_config
from defaults.models import (
    PROVIDER_ANTHROPIC,
    PROVIDER_DEEPSEEK,
    PROVIDER_OPENAI,
    PROVIDER_OPENROUTER,
    ModelConfig,
)
from engine.game_engine import GameEngine

if TYPE_CHECKING:
    from knowledge.graph import KnowledgeGraph
    from models.game_state import GameState
    from timeline.event import GameEvent


def _resolve_model(
    role: str,
    env_model_id: str,
    cfg: Config,
    overrides: dict[str, ModelConfig] | None,
) -> ModelConfig:
    """Return the ModelConfig for a role, preferring overrides over env defaults."""
    if overrides is not None:
        pinned = overrides.get(role)
        if pinned is not None:
            return pinned
    return resolve_model_config(env_model_id)


def create_engine(
    cfg: Config,
    language: str = "English",
    overrides: dict[str, ModelConfig] | None = None,
) -> GameEngine:
    """Build a GameEngine from application config.

    ``overrides`` is an optional role→ModelConfig map (typically produced
    by :func:`engine.model_overrides.load_role_overrides`) that wins over
    ``cfg.<role>_model`` env defaults. Callers that don't have a repo
    handy (CLI one-shot, tests) can omit it for env-only behaviour.
    """
    api_keys = {
        PROVIDER_OPENAI: cfg.openai_api_key,
        PROVIDER_ANTHROPIC: cfg.anthropic_api_key,
        PROVIDER_OPENROUTER: cfg.openrouter_api_key,
        PROVIDER_DEEPSEEK: cfg.deepseek_api_key,
    }
    return GameEngine(
        director_model=_resolve_model("director", cfg.director_model, cfg, overrides),
        agent_model=_resolve_model("agent", cfg.agent_model, cfg, overrides),
        narrator_model=_resolve_model("narrator", cfg.narrator_model, cfg, overrides),
        dramaturge_model=_resolve_model("dramaturge", cfg.dramaturge_model, cfg, overrides)
        if cfg.dramaturge_enabled
        else None,
        api_keys=api_keys,
        language=language,
    )


async def create_engine_from_state(
    cfg: Config,
    game_state: "GameState",
    knowledge_graph: "KnowledgeGraph",
    events: "list[GameEvent]",
    language: str = "English",
) -> GameEngine:
    """Build a GameEngine and restore it from previously saved state.

    DB admin-settings overrides are intentionally NOT consulted here:
    a restored game keeps the models it started with (as derived from
    env/Config), so operator model switches only affect new games.
    """
    engine = create_engine(cfg, language, None)
    await engine.restore_session(game_state, knowledge_graph, events)
    return engine
