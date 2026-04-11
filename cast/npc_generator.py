"""NPC Generator — creates detailed NPC cards."""

from __future__ import annotations

import asyncio
from typing import Any

from cast.base_performer_class import BasePerformer
from cast.schemas.npc_response import NPCResponse
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

        tasks = (self._generate_npc(req, game_state) for req in input_data)
        npcs = await asyncio.gather(*tasks)
        return list(npcs)

    async def _generate_npc(self, npc_request: str, game_state: Any) -> NPCCard:
        """Generate a single NPC card from a role description."""
        prompt = NPC_GENERATOR_CREATE.render(npc_request=npc_request)
        npc_data = await self._send_json(prompt, response_model=NPCResponse)

        return NPCCard(
            name=npc_data.name or "Unknown",
            biography=npc_data.biography,
            appearance=npc_data.appearance,
            occupation=npc_data.occupation or npc_request,
            personality_traits=npc_data.personality_traits,
            speech_style=npc_data.speech_style or "neutral",
            knowledge_scope=npc_data.knowledge_scope or "local",
            attributes=npc_data.attributes,
            inventory=npc_data.inventory,
            location_id=(game_state.current_scene.location_id if game_state.current_scene else None),
        )
