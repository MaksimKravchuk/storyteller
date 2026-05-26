"""Read benchmark-mode engine temperature overrides from environment variables.

Two env-var shapes are supported:

- ``BENCHMARK_TEMPERATURE_OVERRIDE`` — applies the same float to every engine
  role (director, agent, narrator, dramaturge).
- ``BENCHMARK_<ROLE>_TEMPERATURE`` — per-role override, e.g.
  ``BENCHMARK_DIRECTOR_TEMPERATURE=0.0``.  Per-role wins over the global value.

Returns ``None`` when no override is configured, preserving production
behaviour: the engine uses the temperature each ``ModelConfig`` carries.
"""

from __future__ import annotations

import os

_ROLES = ("director", "agent", "narrator", "dramaturge")
_GLOBAL_VAR = "BENCHMARK_TEMPERATURE_OVERRIDE"
_ROLE_VAR_TEMPLATE = "BENCHMARK_{role}_TEMPERATURE"


def _parse_float(raw: str | None) -> float | None:
    """Return a float from ``raw``, or ``None`` if absent or unparseable."""
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _resolve_role_temp(role: str, global_temp: float | None) -> float | None:
    """Pick the temperature for ``role``: per-role var wins, else the global value."""
    per_role_var = _ROLE_VAR_TEMPLATE.format(role=role.upper())
    per_role = _parse_float(os.environ.get(per_role_var))
    return global_temp if per_role is None else per_role


def load_temperature_overrides() -> dict[str, float] | None:
    """Return a ``{role: temperature}`` dict when any override env var is set.

    Returns ``None`` when neither global nor per-role variables are present,
    so callers can cheaply check ``if overrides is None`` before branching.
    """
    global_temp = _parse_float(os.environ.get(_GLOBAL_VAR))

    role_temps: dict[str, float] = {}
    for role in _ROLES:
        candidate = _resolve_role_temp(role, global_temp)
        if candidate is not None:
            role_temps[role] = candidate

    return role_temps if role_temps else None
