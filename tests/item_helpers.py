"""Shared ItemGenerator-related test helpers.

Kept separate from :mod:`tests.director_helpers` so the Director test
factory stays under its module-import budget.
"""

from __future__ import annotations

from typing import Any

from cast.schemas.item_response import ObjectInteractionResponse


async def default_item_generator_execute(input_data: Any, context: dict | None = None) -> Any:
    """Mode-aware stub for ItemGenerator.execute used by test fixtures.

    Returns an :class:`ObjectInteractionResponse` when the call is in
    ``interact`` mode (KER-13 INTERACT-with-object turns) so the
    downstream persist/emit pipeline treats the turn as a no-op
    without raising. Other modes (``batch``, ``examine``) keep the
    pre-KER-13 empty-list default.
    """
    mode = (context or {}).get("mode")
    if mode == "interact":
        return ObjectInteractionResponse(narration="", delta="")
    return []
