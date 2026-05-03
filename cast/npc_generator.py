"""NPC Generator — creates detailed NPC cards."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from loguru import logger

from cast._npc_generator_goals import build_life_goal, candidate_goal_targets
from cast._scene_location import UNKNOWN_SCENE_LOCATION
from cast.base_performer_class import BasePerformer
from cast.schemas.npc_response import NPCGoalDraft, NPCResponse
from models.npc_card import NPCCard
from prompts.npc_generator_prompts import get_npc_generator_prompts

_SETTING_SUMMARY_MAX = 500
_SCENE_DESC_MAX = 200
_SOCIAL_STRUCTURE_MAX = 300
_SHORT_DESCRIPTOR_MAX = 80


def _sanitize_short_descriptor(raw: str, npc_request: str) -> str:
    """Normalise the LLM-supplied ``short_descriptor`` for the NPC card.

    Strips whitespace and truncates to :data:`_SHORT_DESCRIPTOR_MAX`.
    An oversize raw value is logged at ``warning`` — the prompt already
    advertises the ≤80-char cap, so a sustained rate of truncations
    signals a prompt regression worth investigating, mirroring the
    ``_disambiguate_name`` escalation pattern below.
    """
    trimmed = raw.strip()
    if len(trimmed) > _SHORT_DESCRIPTOR_MAX:
        logger.warning(
            "NPCGenerator: short_descriptor for role '{0}' was {1} chars, truncating to {2}",
            npc_request,
            len(trimmed),
            _SHORT_DESCRIPTOR_MAX,
        )
    return trimmed[:_SHORT_DESCRIPTOR_MAX]


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


def _render_vars_for(npc_request: str, game_state: Any, taken_names: set[str]) -> dict[str, str]:
    """Build the dict the create-template's render expects, dropping empty optionals.

    Pulled out of :meth:`NPCGenerator._generate_npc` to keep that method
    inside its WPS210 local-variable budget.
    """
    render_vars: dict[str, str] = {"npc_request": npc_request}
    if taken_names:
        render_vars["forbidden_names"] = ", ".join(sorted(taken_names))
    candidate_targets = candidate_goal_targets(game_state)
    if candidate_targets:
        render_vars["candidate_targets"] = ", ".join(candidate_targets)
    return render_vars


def _resolve_npc_location_id(game_state: Any) -> UUID | None:
    """Resolve a real ``location_id`` for a freshly generated NPC.

    NPCs are physical beings, never ghosts: they belong at the scene's
    location. When the SceneBuilder failed to bind the scene to a
    registered location it leaves the all-zero
    :data:`UNKNOWN_SCENE_LOCATION` sentinel on ``Scene.location_id``;
    persisting that onto the NPC produces the
    ``00000000-0000-0000-0000-000000000000`` rows we used to see in
    ``npcs.location_id``. Fall back to the player's location instead —
    NPCs are always generated in the scene the player is in, so this
    is the truthful choice.
    """
    scene = game_state.current_scene
    if scene and scene.location_id != UNKNOWN_SCENE_LOCATION:
        return scene.location_id
    player_loc = getattr(game_state.player, "location_id", None) if game_state.player else None
    if scene and player_loc:
        logger.warning(
            "NPCGenerator: scene.location_id is unknown sentinel; falling back to player location {0}",
            player_loc,
        )
    return player_loc


def _card_from_response(npc_data: NPCResponse, npc_request: str, game_state: Any) -> NPCCard:
    """Project an :class:`NPCResponse` into a fresh :class:`NPCCard`.

    Stamps ``location_id`` from the current scene (the LLM never produces
    one), refusing the unknown-scene sentinel so NPCs aren't ghosts.
    """
    return NPCCard(
        name=npc_data.name or "Unknown",
        biography=npc_data.biography,
        appearance=npc_data.appearance,
        short_descriptor=_sanitize_short_descriptor(npc_data.short_descriptor, npc_request),
        occupation=npc_data.occupation or npc_request,
        personality_traits=npc_data.personality_traits,
        speech_style=npc_data.speech_style or "neutral",
        knowledge_scope=npc_data.knowledge_scope or "local",
        attributes=npc_data.attributes.model_dump(),
        inventory=npc_data.inventory,
        location_id=_resolve_npc_location_id(game_state),
    )


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

    def __init__(self, *, llm_client: Any, language: str = "English"):
        prompts = get_npc_generator_prompts(language)
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=prompts.system,
        )
        self._create_template = prompts.create
        self.set_context(language=language)

    async def act(self, input_data: list[str], context: dict) -> list[NPCCard]:
        """Generate NPC cards.

        ``input_data``: List of NPC role descriptions (e.g. ["tavern merchant", "city guard"]).
        ``context``: Must contain ``game_state``.

        Returns a list of ``NPCCard`` objects. Generation is serial so each
        call can tell the LLM which names have already been handed out in
        this batch — otherwise two parallel roles with identical context
        routinely mode-collapse onto the same name. At most one NPC per
        batch is allowed to carry a life-tier goal so a single generation
        pass cannot flood the world with vengeance arcs.
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

        return await self._generate_batch(
            list(input_data),
            game_state,
            _existing_scene_names(game_state),
        )

    async def _generate_batch(
        self,
        pending: list[str],
        game_state: Any,
        taken_names: set[str],
    ) -> list[NPCCard]:
        """Serially drain ``pending``, spending the per-batch goal budget at most once."""
        goal_budget = 1
        cards: list[NPCCard] = []
        while pending:
            card, goal_budget = await self._generate_with_goal_budget(
                pending.pop(0),
                game_state,
                taken_names,
                goal_budget,
            )
            cards.append(card)
        return cards

    async def _generate_with_goal_budget(
        self,
        npc_request: str,
        game_state: Any,
        taken_names: set[str],
        goal_budget: int,
    ) -> tuple[NPCCard, int]:
        """Generate one card; spend ``goal_budget`` to attach a life-goal at most once per batch."""
        card, goal_draft = await self._generate_unique(npc_request, game_state, taken_names)
        if goal_draft is None or goal_budget <= 0:
            return card, goal_budget
        life_goal = build_life_goal(goal_draft, game_state, npc_request)
        if life_goal is None:
            return card, goal_budget
        card.life_goal = life_goal
        return card, goal_budget - 1

    async def _generate_unique(
        self,
        npc_request: str,
        game_state: Any,
        taken_names: set[str],
    ) -> tuple[NPCCard, NPCGoalDraft | None]:
        """Generate one card and rename it if the LLM ignored ``forbidden_names``.

        The rename is logged at ``error`` because downstream name-matchers
        (dialogue targeting, interaction filters) compare ``npc.name.lower()``
        and will silently miss the suffixed form — a sustained rate of renames
        signals a prompt regression worth investigating.

        Returns the card alongside the raw goal draft (if any) so the
        caller can apply per-batch rate-limiting before turning the draft
        into a :class:`Goal`.
        """
        card, goal_draft = await self._generate_npc(npc_request, game_state, taken_names)
        if card.name in taken_names:
            disambiguated = _disambiguate_name(card.name, card.occupation, taken_names)
            logger.error(
                "NPCGenerator: LLM returned taken name '{0}' for role '{1}', renaming to '{2}'",
                card.name,
                npc_request,
                disambiguated,
            )
            card.name = disambiguated
        taken_names.add(card.name)
        return card, goal_draft

    async def _generate_npc(
        self,
        npc_request: str,
        game_state: Any,
        taken_names: set[str],
    ) -> tuple[NPCCard, NPCGoalDraft | None]:
        """Generate a single NPC card from a role description."""
        prompt = self._create_template.render(**_render_vars_for(npc_request, game_state, taken_names))
        npc_data = await self._send_json(prompt, response_model=NPCResponse)
        return _card_from_response(npc_data, npc_request, game_state), npc_data.goal
