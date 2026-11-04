"""Factory functions to create a GameEngine from Config."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

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


def _resolve_search_client(cfg: Config, search_override: Any) -> Any:
    """Build the search client, letting a DB ``search_override`` win over env.

    The override (from :func:`engine.search_settings.load_search_override`)
    supplies the provider and, when present, its credentials; anything it
    leaves unset falls back to the ``cfg.search_*`` env defaults.
    """
    provider = cfg.search_provider
    tavily_api_key = cfg.tavily_api_key
    searxng_base_url = cfg.searxng_base_url
    if search_override is not None and search_override.provider:
        provider = search_override.provider
        tavily_api_key = search_override.tavily_api_key or tavily_api_key
        searxng_base_url = search_override.searxng_base_url or searxng_base_url
    return create_search_client(provider, tavily_api_key=tavily_api_key, searxng_base_url=searxng_base_url)


def create_engine(
    cfg: Config,
    language: str = "English",
    overrides: dict[str, ModelConfig] | None = None,
    *,
    temperature_override: dict[str, float] | None = None,
    search_override: Any = None,
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
    search_client = _resolve_search_client(cfg, search_override)
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

    DB admin-settings overrides are NOT consulted here (no repo access);
    web callers go through ``engine.session_ops.restore_engine_with_admin_settings``.

    The benchmark harness's temperature-pinning path does NOT use this
    helper — it calls :func:`create_engine` with ``temperature_override``
    and ``restore_session`` separately, see ``benchmarks/harness/_run_execution.py``.
    """
    engine = create_engine(cfg, language, None)
    await engine.restore_session(game_state, knowledge_graph, events)
    return engine
