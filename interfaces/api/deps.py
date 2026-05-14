"""FastAPI dependency providers for the mobile API.

Module-level singletons are returned by the providers so route handlers
and tests can rebind them via ``app.dependency_overrides`` without
needing to thread them through every constructor.
"""

from __future__ import annotations

from interfaces.api.engine_factory import DefaultEngineFactory, EngineFactory
from interfaces.api.sessions import SessionStore

_store = SessionStore()
_engine_factory: EngineFactory = DefaultEngineFactory()


def get_session_store() -> SessionStore:
    """Return the process-local ``SessionStore`` singleton."""
    return _store


def get_engine_factory() -> EngineFactory:
    """Return the engine factory used to build new sessions."""
    return _engine_factory
