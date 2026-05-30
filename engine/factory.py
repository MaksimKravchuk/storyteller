"""Factory functions to create a GameEngine from Config."""

from __future__ import annotations

import dataclasses
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
from research.search_factory import create_search_client
from safety.factory import build_moderator

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


def _apply_temperature(model_config: ModelConfig, temperature: float | None) -> ModelConfig:
    """Return a new ModelConfig with the given temperature, or unchanged if None."""
    if temperature is None:
        return model_config
    return dataclasses.replace(model_config, temperature=temperature)


def create_engine(
    cfg: Config,
    language: str = "English",
    overrides: dict[str, ModelConfig] | None = None,
    *,
    temperature_override: dict[str, float] | None = None,
) -> GameEngine:
    """Build a GameEngine from application config.

    ``overrides`` is an optional role→ModelConfig map (typically produced
    by :func:`engine.model_overrides.load_role_overrides`) that wins over
    ``cfg.<role>_model`` env defaults. Callers that don't have a repo
    handy (CLI one-shot, tests) can omit it for env-only behaviour.

    ``temperature_override`` is an optional role→float map used exclusively
    by the benchmark harness to pin temperature and reduce run-to-run variance.
    Production callers must not pass it — omitting it preserves the temperature
    each ``ModelConfig`` carries from ``config.py``.
    """
    temps = temperature_override or {}
    api_keys = {
        PROVIDER_OPENAI: cfg.openai_api_key,
        PROVIDER_ANTHROPIC: cfg.anthropic_api_key,
        PROVIDER_OPENROUTER: cfg.openrouter_api_key,
        PROVIDER_DEEPSEEK: cfg.deepseek_api_key,
    }
    search_client = create_search_client(
        cfg.search_provider,
        tavily_api_key=cfg.tavily_api_key,
        searxng_base_url=cfg.searxng_base_url,
    )
    return GameEngine(
        director_model=_apply_temperature(
            _resolve_model("director", cfg.director_model, cfg, overrides),
            temps.get("director"),
        ),
        agent_model=_apply_temperature(
            _resolve_model("agent", cfg.agent_model, cfg, overrides),
            temps.get("agent"),
        ),
        narrator_model=_apply_temperature(
            _resolve_model("narrator", cfg.narrator_model, cfg, overrides),
            temps.get("narrator"),
        ),
        dramaturge_model=_apply_temperature(
            _resolve_model("dramaturge", cfg.dramaturge_model, cfg, overrides),
            temps.get("dramaturge"),
        )
        if cfg.dramaturge_enabled
        else None,
        api_keys=api_keys,
        language=language,
        moderator=build_moderator(cfg),
        search_client=search_client,
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

    The benchmark harness's temperature-pinning path does NOT use this
    helper — it calls :func:`create_engine` with ``temperature_override``
    and ``restore_session`` separately, see ``benchmarks/harness/_run_execution.py``.
    """
    engine = create_engine(cfg, language, None)
    await engine.restore_session(game_state, knowledge_graph, events)
    return engine
