"""Engine factory dependency for the mobile API.

Wrapped behind a Protocol so route handlers can be tested with a
``Director``-less mock instead of building a real LLM-backed engine.
"""

from __future__ import annotations

from typing import Protocol

from config import load_config
from engine.factory import create_engine
from engine.game_engine import GameEngine


class EngineFactory(Protocol):
    """Builds a ``GameEngine`` for a new session."""

    def build(self, language: str) -> GameEngine:
        """Return a fresh, un-started ``GameEngine``."""


class DefaultEngineFactory:
    """Production factory — wires a ``GameEngine`` from the loaded ``Config``."""

    def build(self, language: str) -> GameEngine:
        """Return a fresh ``GameEngine`` configured from ``load_config()``."""
        return create_engine(load_config(), language=language)
