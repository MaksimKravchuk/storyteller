"""Hybrid time-cost system.

Base costs are predefined per action type; the Director's LLM can
override them when context demands it (e.g. long-distance travel).
"""

from __future__ import annotations

import types

# Base time costs in hours, keyed by action type (uppercase)
BASE_ACTION_COSTS: types.MappingProxyType[str, float] = types.MappingProxyType(
    {
        "TALK": 0.05,  # ~3 minutes — a quick exchange
        "EXPLORE": 0.5,  # 30 minutes
        "EXAMINE": 0.01,  # ~30 seconds — a glance
        "INTERACT": 0.02,  # ~1 minute — grab, push, open
        "SLEEP": 8.0,
        "MOVE": 0.5,  # 30 min local; LLM should override for long distance
        "WAIT": 0.1,  # ~6 minutes — passing time while idle
        "OTHER": 0.02,  # ~1 minute
    }
)


def resolve_time_cost(
    action_type: str,
    llm_override: float | None = None,
) -> float:
    """Return the effective time cost for an action.

    If the LLM provided an override (e.g. "travel to distant city" = 48h),
    use that.  Otherwise fall back to the base cost for the action type.
    """
    if llm_override is not None and llm_override > 0:
        return llm_override
    return BASE_ACTION_COSTS.get(action_type.upper(), BASE_ACTION_COSTS["OTHER"])
