"""Schemas for the Item Generator LLM JSON responses."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ItemListResponse(BaseModel):
    """Typed view of the batch-expansion Item Generator response.

    Mirrors ``cast/item_generator.py::_expand_inventory`` which reads
    ``response.get("items", [])``. The schema field is named
    ``expanded`` to avoid shadowing ``dict.items``; the LLM still
    emits the JSON key ``items``, routed here via ``alias``.
    """

    model_config = ConfigDict(populate_by_name=True)

    expanded: list[str] = Field(default_factory=list, alias="items")


class ItemExamineResponse(BaseModel):
    """Typed view of the single-item examination response.

    Mirrors ``cast/item_generator.py::_examine_item`` which reads
    ``response.get("description", item_name)``. The schema default is
    the empty string; the caller still falls back to the item name
    when the LLM omits the description.
    """

    description: str = ""


class ObjectInteractionResponse(BaseModel):
    """Typed view of the object-interaction response (KER-13).

    ``narration`` is the short physical description of what the player
    did to the object — handed to the Narrator as part of the turn
    raw material. ``delta`` is the persistent state change that lives
    on as a ``scene_state``-tagged :class:`knowledge.node.KnowledgeNode`
    so future visits to the same location reflect the change.

    Both fields default to the empty string; the caller treats an
    empty ``delta`` as "no persistent change" and skips the graph
    write in that case.
    """

    narration: str = ""
    delta: str = ""
