"""Shared ItemGenerator-related test helpers."""

from __future__ import annotations

from typing import Any

from cast.schemas.item_response import ObjectInteractionResponse


async def default_item_generator_execute(input_data: Any, context: dict | None = None) -> Any:
    """Mode-aware stub for ItemGenerator.execute used by test fixtures.

    ``interact`` mode expects a typed response the downstream pipeline
    can persist; other modes expect a list. Returning the wrong shape
    raises downstream, so the stub branches on mode.
    """
    mode = (context or {}).get("mode")
    if mode == "interact":
        return ObjectInteractionResponse(narration="", delta="")
    return []
