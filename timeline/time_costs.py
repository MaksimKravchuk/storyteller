"""Hybrid time-cost system.

Base costs are predefined per action type; the Director's LLM can
override them when context demands it (e.g. long-distance travel).
"""

from __future__ import annotations


# Base time costs in hours, keyed by action type (uppercase)
BASE_ACTION_COSTS: dict[str, float] = {
    "TALK": 0.5,
    "EXPLORE": 1.0,
    "EXAMINE": 0.25,
    "INTERACT": 0.5,
    "SLEEP": 8.0,
    "MOVE": 1.0,      # Default for local movement; LLM should override for long distance
    "OTHER": 0.5,
}


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
