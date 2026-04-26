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
from engine.game_engine import EngineModels, GameEngine

if TYPE_CHECKING:
    from db.repository import GameRepository
    from knowledge.graph import KnowledgeGraph
    from models.game_state import GameState
    from timeline.event import GameEvent


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
    return _build_engine(cfg, language, overrides)


async def create_engine_with_db_overrides(
    repo: "GameRepository",
    cfg: Config,
    language: str = "English",
) -> GameEngine:
    """Convenience: read DB role overrides for ``repo`` and build an engine.

    One-shot helper for callers that both have a repository handy and
    want admin-panel model overrides applied — i.e. telegram + web new-game
    paths. Keeps their import count small by collapsing two imports (``create_engine``
    + ``load_role_overrides``) into one.
    """
    from engine.model_overrides import load_role_overrides

    overrides = await load_role_overrides(repo, cfg)
    return _build_engine(cfg, language, overrides)


async def create_engine_from_state(
    cfg: Config,
    game_state: GameState,
    knowledge_graph: KnowledgeGraph,
    events: list[GameEvent],
    language: str = "English",
) -> GameEngine:
    """Build a GameEngine and restore it from previously saved state.

    DB admin-settings overrides are intentionally NOT consulted here:
    a restored game keeps the models it started with (as derived from
    env/Config), so operator model switches only affect new games.
    """
    engine = _build_engine(cfg, language, None)
    await engine.restore_session(game_state, knowledge_graph, events)
    return engine


def _resolve_role(
    role: str,
    env_model_id: str,
    cfg: Config,
    overrides: dict[str, ModelConfig] | None,
) -> ModelConfig:
    if overrides is not None:
        pinned = overrides.get(role)
        if pinned is not None:
            return pinned
    return resolve_model_config(env_model_id, cfg)


def _assemble_models(cfg: Config, overrides: dict[str, ModelConfig] | None) -> EngineModels:
    return EngineModels(
        director=_resolve_role("director", cfg.director_model, cfg, overrides),
        agent=_resolve_role("agent", cfg.agent_model, cfg, overrides),
        narrator=_resolve_role("narrator", cfg.narrator_model, cfg, overrides),
        dramaturge=(
            _resolve_role("dramaturge", cfg.dramaturge_model, cfg, overrides) if cfg.dramaturge_enabled else None
        ),
    )


def _build_engine(
    cfg: Config,
    language: str,
    overrides: dict[str, ModelConfig] | None,
) -> GameEngine:
    api_keys = {
        PROVIDER_OPENAI: cfg.openai_api_key,
        PROVIDER_ANTHROPIC: cfg.anthropic_api_key,
        PROVIDER_OPENROUTER: cfg.openrouter_api_key,
        PROVIDER_DEEPSEEK: cfg.deepseek_api_key,
    }
    return GameEngine(
        models=_assemble_models(cfg, overrides),
        api_keys=api_keys,
        language=language,
    )
