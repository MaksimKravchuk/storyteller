"""Readiness helpers for the public web demo."""

from __future__ import annotations

from fastapi import status
from fastapi.responses import JSONResponse

from config import Config, get_api_key_for_provider, resolve_model_config

_READINESS_MISSING_CREDENTIALS = "Storyteller is not ready to start games: missing LLM provider credentials."


def required_llm_providers(cfg: Config) -> list[str]:
    """Return the distinct LLM providers required to start and narrate a game."""
    model_ids = [cfg.director_model, cfg.agent_model, cfg.narrator_model]
    if cfg.dramaturge_enabled:
        model_ids.append(cfg.dramaturge_model)
    return sorted({resolve_model_config(model_id).provider for model_id in model_ids})


def readiness_payload(cfg: Config) -> dict[str, object] | JSONResponse:
    """Return readiness JSON for dependencies needed by player-startable games."""
    required_providers = required_llm_providers(cfg)
    missing_providers = [provider for provider in required_providers if not get_api_key_for_provider(provider, cfg)]
    if missing_providers:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unavailable",
                "required_providers": required_providers,
                "missing_providers": missing_providers,
                "detail": _READINESS_MISSING_CREDENTIALS,
            },
        )
    return {
        "status": "ok",
        "required_providers": required_providers,
        "missing_providers": [],
    }
