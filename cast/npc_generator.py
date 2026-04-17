"""NPC Generator — creates detailed NPC cards."""

from __future__ import annotations

from typing import Any

from loguru import logger

from cast.base_performer_class import BasePerformer
from cast.schemas.npc_response import NPCResponse
from models.npc_card import NPCCard
from prompts.npc_generator_prompts import NPC_GENERATOR_CREATE, NPC_GENERATOR_SYSTEM

_SETTING_SUMMARY_MAX = 500
_SCENE_DESC_MAX = 200
_SOCIAL_STRUCTURE_MAX = 300


def _existing_scene_names(game_state: Any) -> set[str]:
    """Collect names of NPCs already materialised in the current scene."""
    scene = getattr(game_state, "current_scene", None)
    if not scene:
        return set()
    taken: set[str] = set()
    for scene_npc in scene.npcs_present:
        card = game_state.npcs.get(scene_npc.uuid) if scene_npc.uuid else None
        if card and card.name:
            taken.add(card.name)
    return taken


def _disambiguate_name(name: str, occupation: str, taken: set[str]) -> str:
    """Return a name that does not collide with any name in ``taken``.

    Applied as a last-resort safety net when the LLM ignores the
    ``forbidden_names`` prompt section and returns a duplicate anyway.
    Deterministic so collisions in tests are reproducible.
    """
    base = "{0} ({1})".format(name, occupation) if occupation else name
    candidate = base
    suffix = 2
    while candidate in taken:
        candidate = "{0} [{1}]".format(base, suffix)
        suffix += 1
    return candidate


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

        Returns a list of ``NPCCard`` objects. Generation is serial so each
        call can tell the LLM which names have already been handed out in
        this batch — otherwise two parallel roles routinely collapse onto the
        same random-seeded name.
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

        taken_names = _existing_scene_names(game_state)
        cards: list[NPCCard] = []
        pending = list(input_data)
        while pending:
            cards.append(await self._generate_unique(pending.pop(0), game_state, taken_names))
        return cards

    async def _generate_unique(self, npc_request: str, game_state: Any, taken_names: set[str]) -> NPCCard:
        """Generate one card and rename it if the LLM ignored ``forbidden_names``."""
        card = await self._generate_npc(npc_request, game_state, taken_names)
        if card.name in taken_names:
            disambiguated = _disambiguate_name(card.name, card.occupation, taken_names)
            logger.warning(
                "NPCGenerator: LLM returned taken name '{0}' for role '{1}', renaming to '{2}'",
                card.name,
                npc_request,
                disambiguated,
            )
            card.name = disambiguated
        taken_names.add(card.name)
        return card

    async def _generate_npc(self, npc_request: str, game_state: Any, taken_names: set[str]) -> NPCCard:
        """Generate a single NPC card from a role description."""
        render_vars = {"npc_request": npc_request}
        if taken_names:
            render_vars["forbidden_names"] = ", ".join(sorted(taken_names))
        prompt = NPC_GENERATOR_CREATE.render(**render_vars)
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
