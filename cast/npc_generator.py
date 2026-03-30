"""NPC Generator — creates detailed NPC cards."""

from __future__ import annotations

from typing import Any

from cast.base_performer_class import BasePerformer
from models.npc_card import NPCCard
from prompts.npc_generator_prompts import NPC_GENERATOR_CREATE, NPC_GENERATOR_SYSTEM

_SETTING_SUMMARY_MAX = 500
_SCENE_DESC_MAX = 200
_SOCIAL_STRUCTURE_MAX = 300


class NPCGenerator(BasePerformer):
    """Creates NPC cards with bio, appearance, knowledge level, etc."""

    def __init__(self, *, llm_client: Any):
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=NPC_GENERATOR_SYSTEM,
        )

    async def act(self, input_data: list[str], context: dict) -> list[NPCCard]:
        """Generate NPC cards.

        ``input_data``: List of NPC role descriptions (e.g. ["tavern merchant", "city guard"]).
        ``context``: Must contain ``game_state``.

        Returns a list of ``NPCCard`` objects.
        """
        from models.game_state import GameState

        game_state: GameState = context["game_state"]

        self.set_context(
            setting_summary=game_state.setting.summary[:_SETTING_SUMMARY_MAX],
            location_name=(
                game_state.current_scene.description[:_SCENE_DESC_MAX]
                if game_state.current_scene
                else "Unknown location"
            ),
            social_structure=game_state.setting.social_structure[:_SOCIAL_STRUCTURE_MAX],
        )

        npcs: list[NPCCard] = []
        for npc_request in input_data:
            prompt = NPC_GENERATOR_CREATE.render(npc_request=npc_request)
            npc_data = await self._send_json(prompt)

            card = NPCCard(
                name=npc_data.get("name", "Unknown"),
                biography=npc_data.get("biography", ""),
                appearance=npc_data.get("appearance", ""),
                occupation=npc_data.get("occupation", npc_request),
                personality_traits=npc_data.get("personality_traits", []),
                speech_style=npc_data.get("speech_style", "neutral"),
                knowledge_scope=npc_data.get("knowledge_scope", "local"),
                attributes=npc_data.get("attributes", {}),
                inventory=npc_data.get("inventory", []),
                location_id=(game_state.current_scene.location_id if game_state.current_scene else None),
            )
            npcs.append(card)

        return npcs
