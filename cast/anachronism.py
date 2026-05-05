"""AnachronismClassifier and per-turn modifier helpers.

The classifier is invoked at most once per turn (see
:meth:`cast.director_dialogue.DialogueHandler.handle_dialogue`). Its
verdict is cached on a :class:`TurnAnachronismContext` and re-read
per-NPC by :func:`cast._anachronism_math.build_npc_result`, which
applies the education + familiarity discount described in issue #186
before the dice contest reads ``effective_strangeness``.

Why a separate context object instead of plumbing the verdict
directly through call-site arguments:

* Object interactions need read-only access to the same verdict for
  telemetry, but they live in a different sub-handler than dialogue.
  Passing the context is cheaper than threading every field through
  two parallel call paths.
* The classifier call is genuinely expensive (one LLM round trip),
  so caching is load-bearing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from cast._anachronism_math import (
    build_npc_result,
    empty_classification,
    format_inventory,
    format_seeds,
)
from cast.base_performer_class import BasePerformer
from cast.schemas.anachronism import AnachronismClassification, NPCAnachronismResult
from llm.base_client import BaseLLMClient, LLMJSONError
from loguru import logger
from prompts.anachronism_classifier import (
    ANACHRONISM_CLASSIFIER_SYSTEM,
    ANACHRONISM_CLASSIFIER_TASK,
)

if TYPE_CHECKING:
    from knowledge.query import KnowledgeQueryEngine
    from models.game_state import GameState

# An empty string disables the classifier; this constant exists so the
# guard reads as "explicit feature flag" rather than a magic empty-string
# check at every callsite.
_DISABLED_ORIGIN_ERA = ""


@dataclass
class TurnAnachronismContext:
    """Per-turn anachronism cache shared across dialogue + object-interaction paths.

    The classifier runs at most once: the first ``await ensure_base()``
    triggers the LLM call, every later read sees the cached verdict.
    Both ``handle_dialogue`` and the object-interaction telemetry path
    consume this cache so a multi-NPC scene plus an INTERACT target
    pay one classifier round trip in total.

    ``base`` starts ``None`` until ``ensure_base()`` runs; downstream
    helpers must read through the :attr:`base_or_empty` property
    (returns the no-classification sentinel until populated) so callers
    don't have to special-case "did the classifier ever fire on this
    turn?".
    """

    classifier: AnachronismClassifier
    query_engine: KnowledgeQueryEngine
    player_action: str
    game_state: GameState
    base: AnachronismClassification | None = field(default=None)

    async def ensure_base(self) -> AnachronismClassification:
        """Idempotent classifier invocation; subsequent calls return the cache."""
        if self.base is None:
            self.base = await self.classifier.classify(self.player_action, self.game_state)
        return self.base

    @property
    def base_or_empty(self) -> AnachronismClassification:
        """Return the cached verdict, or the empty sentinel if not yet classified."""
        return self.base or empty_classification()

    def for_npc(self, npc: Any) -> NPCAnachronismResult:
        """Return the per-NPC modulated view of the cached verdict."""
        return build_npc_result(self.base_or_empty, npc, self.query_engine)

    @classmethod
    def create_for(
        cls,
        classifier: AnachronismClassifier,
        game_state: GameState,
        player_action: str,
    ) -> TurnAnachronismContext:
        """Build a context bound to *game_state*'s knowledge graph.

        Centralises the :class:`KnowledgeQueryEngine` construction so
        the executor doesn't need to import the query module just to
        wire one up — keeps callers slim under the WPS module-import
        budget.
        """
        from knowledge.query import KnowledgeQueryEngine

        return cls(
            classifier=classifier,
            query_engine=KnowledgeQueryEngine(game_state.knowledge_graph),
            player_action=player_action,
            game_state=game_state,
        )


class AnachronismClassifier(BasePerformer):
    """LLM performer that judges whether a player action is out of period.

    Returns the empty verdict (score 0, no concepts, no rewrite) when
    ``player.origin_era`` is empty so a same-era playthrough pays no
    LLM cost. LLM-side failures (validation errors, timeouts, etc.)
    also degrade to the empty verdict — the turn must keep moving even
    if the classifier silently breaks.
    """

    def __init__(self, *, llm_client: BaseLLMClient):
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=ANACHRONISM_CLASSIFIER_SYSTEM,
        )

    async def act(self, input_data: str, context: dict) -> AnachronismClassification:
        """BasePerformer entry-point — equivalent to :meth:`classify`.

        Most callers use :meth:`classify` directly because the cached
        ``TurnAnachronismContext`` already carries the game state. The
        ``act`` shim exists for parity with the other performers (so a
        future RemoteTrigger / scheduler can drive it).
        """
        return await self.classify(input_data, context["game_state"])

    async def classify(self, player_action: str, game_state: GameState) -> AnachronismClassification:
        """Run the classifier once for *player_action* against *game_state*.

        Returns the empty sentinel when the player did not declare an
        ``origin_era`` (the deterministic feature flag) and on any LLM
        failure. The fallback path is wide on purpose: a misbehaving
        classifier must never abort the turn — the dice contest still
        rolls, just without the anachronism modifier.
        """
        player = game_state.player
        if player.origin_era == _DISABLED_ORIGIN_ERA:
            return empty_classification()
        self._render_system_context(game_state)
        try:
            return await self._send_json(
                ANACHRONISM_CLASSIFIER_TASK.render(
                    player_action=player_action,
                    player_inventory=format_inventory(player.inventory),
                ),
                response_model=AnachronismClassification,
            )
        except LLMJSONError:
            logger.exception("AnachronismClassifier LLM call failed; degrading to empty verdict")
            return empty_classification()

    def _render_system_context(self, game_state: GameState) -> None:
        """Bind setting + player anchors into the classifier system prompt."""
        setting = game_state.setting
        technologies = ", ".join(setting.technologies) if setting.technologies else "(none recorded)"
        social_structure = setting.social_structure or "(unrecorded)"
        self.set_context(
            setting_name=setting.name,
            time_period=setting.time_period,
            social_structure=social_structure,
            technologies=technologies,
            origin_era=game_state.player.origin_era,
            seed_concepts=format_seeds(),
        )
