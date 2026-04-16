"""Item Generator — creates precise physical descriptions of items."""

from __future__ import annotations

from typing import Any

from cast.base_performer_class import BasePerformer
from cast.schemas.item_response import (
    ItemExamineResponse,
    ItemListResponse,
    ObjectInteractionResponse,
)
from llm.turn_event_logger import record_turn_event
from prompts.item_generator_prompts import (
    ITEM_GENERATOR_BATCH,
    ITEM_GENERATOR_EXAMINE,
    ITEM_GENERATOR_INTERACT,
    ITEM_GENERATOR_SYSTEM,
)

_SETTING_SUMMARY_MAX = 500


class ItemGenerator(BasePerformer):
    """Produces strict, precise item descriptions — no literary flourishes."""

    def __init__(self, *, llm_client: Any):
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=ITEM_GENERATOR_SYSTEM,
        )

    async def act(self, input_data: Any, context: dict) -> Any:
        """Dispatch based on context mode.

        ``context["mode"]``:
            - ``"batch"``: expand a list of bare item names.
              ``input_data``: list of item name strings.
              ``context``: must contain ``game_state`` and ``owner_context``.
            - ``"examine"``: detailed single-item examination.
              ``input_data``: item name string.
              ``context``: must contain ``game_state`` and ``context_hint``.
            - ``"interact"``: resolve a physical INTERACT action on an object.
              ``input_data``: object name string.
              ``context``: must contain ``game_state``, ``player_action`` and
              ``context_hint``. Returns an :class:`ObjectInteractionResponse`
              carrying both narration and the persistent delta.
        """
        mode = context.get("mode", "batch")
        from models.game_state import GameState

        game_state: GameState = context["game_state"]

        if mode == "examine":
            return await self._examine_item(
                item_name=input_data,
                context_hint=context.get("context_hint", ""),
                game_state=game_state,
            )
        if mode == "interact":
            return await self._interact_with_object(
                object_name=input_data,
                player_action=context.get("player_action", ""),
                context_hint=context.get("context_hint", ""),
                game_state=game_state,
            )
        return await self._expand_inventory(
            inventory=input_data,
            owner_context=context.get("owner_context", ""),
            game_state=game_state,
        )

    async def _expand_inventory(
        self,
        inventory: list[str],
        owner_context: str,
        game_state: Any,
    ) -> list[str]:
        """Batch-expand bare item names into precise descriptions."""
        if not inventory:
            return inventory

        self.set_context(setting_summary=game_state.setting.summary[:_SETTING_SUMMARY_MAX])

        formatted_list = "\n".join("- {0}".format(entry) for entry in inventory)
        prompt = ITEM_GENERATOR_BATCH.render(owner_context=owner_context, item_list=formatted_list)
        response = await self._send_json(prompt, response_model=ItemListResponse)
        record_turn_event(
            "item_list",
            {
                "owner_context": owner_context,
                "requested": list(inventory),
                "expanded": list(response.expanded),
            },
        )

        expanded = response.expanded
        if len(expanded) != len(inventory):
            return inventory
        return expanded

    async def _examine_item(
        self,
        item_name: str,
        context_hint: str,
        game_state: Any,
    ) -> str:
        """Generate a detailed physical examination of a single item."""
        self.set_context(setting_summary=game_state.setting.summary[:_SETTING_SUMMARY_MAX])

        prompt = ITEM_GENERATOR_EXAMINE.render(item_name=item_name, context_hint=context_hint)
        response = await self._send_json(prompt, response_model=ItemExamineResponse)
        record_turn_event(
            "item_examine",
            {
                "item_name": item_name,
                "context_hint": context_hint,
                "description": response.description,
            },
        )
        return response.description or item_name

    async def _interact_with_object(
        self,
        object_name: str,
        player_action: str,
        context_hint: str,
        game_state: Any,
    ) -> ObjectInteractionResponse:
        """Resolve a physical INTERACT action against a scene object.

        Produces both the short narration the Narrator will inline and
        the persistent ``delta`` string that the caller writes to the
        knowledge graph as a ``scene_state`` node. An empty ``delta``
        means "no lasting change" and signals the caller to skip the
        graph write.
        """
        self.set_context(setting_summary=game_state.setting.summary[:_SETTING_SUMMARY_MAX])

        prompt = ITEM_GENERATOR_INTERACT.render(
            player_action=player_action,
            object_name=object_name,
            context_hint=context_hint,
        )
        return await self._send_json(prompt, response_model=ObjectInteractionResponse)
