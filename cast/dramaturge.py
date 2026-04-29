"""Dramaturge — consistency oracle for Narrator output.

The Dramaturge is a read-only performer that reviews freshly-narrated
text for factual contradictions against the knowledge graph and the
current scene's conversation log. It rewrites sentences that disagree
with historical canon or prior NPC statements and passes everything
else through untouched.

It is **not** a story editor. It has no opinion on tone, pacing,
genre, or dramatic shape — that would nudge the sandbox toward a
story, which this engine explicitly avoids. Its only axis of judgment
is factual consistency, and session canon (anything the player caused
to be true this session) always wins over historical canon.
"""

from __future__ import annotations

import asyncio
from typing import Any

from cast.base_performer_class import BasePerformer
from cast.schemas.dramaturge_response import DramaturgeResponse
from knowledge.graph import KnowledgeGraph
from knowledge.node import CanonSource, KnowledgeNode
from loguru import logger
from models.game_state import GameState
from prompts.dramaturge_prompts import get_dramaturge_prompts

_MAX_HISTORICAL_FACTS = 20
_FACT_PREVIEW_CHARS = 240
_MAX_SCENE_HISTORY = 8
_HISTORY_PREVIEW_CHARS = 200
_EMPTY_HISTORY_PLACEHOLDER = "(none)"
_EMPTY_FACTS_PLACEHOLDER = "(none)"


def _format_fact_bullet(node: KnowledgeNode) -> str:
    """Render one historical-canon node as a single bullet line."""
    return "- {0}".format(node.text[:_FACT_PREVIEW_CHARS])


def _format_historical_facts(graph: KnowledgeGraph) -> str:
    """Render up to ``_MAX_HISTORICAL_FACTS`` historical-canon nodes.

    Session-canon nodes are deliberately excluded so the Dramaturge
    never "rewrites" the player's own accomplishments back out of the
    narration. If the graph has no historical facts we return a short
    placeholder instead of an empty string so the prompt section still
    renders (and the LLM does not wonder where the canon went).
    """
    historical = [node for node in graph.all_nodes() if node.canon == CanonSource.HISTORICAL]
    if not historical:
        return _EMPTY_FACTS_PLACEHOLDER
    capped = historical[:_MAX_HISTORICAL_FACTS]
    return "\n".join(_format_fact_bullet(node) for node in capped)


def _clean_entity_hints(hints: list[str]) -> list[str]:
    """Strip and filter escalation hints before sending them to DataMiner."""
    return [hint.strip() for hint in hints if hint and hint.strip()]


def _format_scene_history(scene_log: list[dict]) -> str:
    """Render the tail of ``scene_conversation_log`` as compact bullets.

    We pull at most ``_MAX_SCENE_HISTORY`` entries and truncate each
    response summary so the prompt stays lean. Empty logs return the
    placeholder rather than an empty string so the prompt section
    renders consistently on new scenes.
    """
    if not scene_log:
        return _EMPTY_HISTORY_PLACEHOLDER
    tail = scene_log[-_MAX_SCENE_HISTORY:]
    lines: list[str] = []
    for entry in tail:
        action = entry.get("player_action", "")
        summary = entry.get("response_summary", "")[:_HISTORY_PREVIEW_CHARS]
        lines.append("- Player: {0} → {1}".format(action, summary))
    return "\n".join(lines)


class Dramaturge(BasePerformer):
    """Consistency oracle that validates Narrator output against canon."""

    def __init__(self, *, llm_client: Any, language: str = "English"):
        prompts = get_dramaturge_prompts(language)
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=prompts.system,
        )
        self._review_template = prompts.review
        self.set_context(language=language)

    async def act(self, input_data: str, context: dict) -> str:
        """Review ``input_data`` and return a consistency-checked narration.

        ``input_data``: The raw narration string produced by the Narrator.

        ``context``: Must contain ``game_state``. Optionally accepts
        ``data_miner`` — when provided, the Dramaturge asks it to
        ``ensure_fact`` any entities the LLM flagged as unknown so
        future turns have them on hand.

        Returns the corrected narration string. The "player must never
        see a half-rewritten passage" invariant is enforced by a single
        broad catch around the entire review path: any exception (LLM
        error, network failure, missing context key, bad game state)
        is logged with its traceback and the original narration is
        returned unchanged. ``asyncio.CancelledError`` is re-raised so
        task cancellation still propagates.
        """
        narration = (input_data or "").strip()
        if not narration:
            return narration
        try:
            verdict = await self._review_narration(narration, context)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Dramaturge review failed; falling back to original narration")
            return narration
        return await self._resolve_verdict(verdict, narration, context)

    async def _review_narration(self, narration: str, context: dict) -> DramaturgeResponse:
        """Assemble context and ask the LLM for a consistency verdict.

        Extracted so ``act()`` can wrap the whole path in a single
        broad catch. Context assembly (``game_state`` lookup, prompt
        formatters, template rendering) and the LLM call itself all
        live here, so a ``KeyError`` / ``AttributeError`` /
        ``APIStatusError`` all land in the same fallback branch.
        """
        game_state: GameState = context["game_state"]
        self.set_context(
            setting_name=game_state.setting.name,
            time_period=game_state.setting.time_period,
            historical_facts=_format_historical_facts(game_state.knowledge_graph),
            scene_history=_format_scene_history(game_state.scene_conversation_log),
        )
        return await self._send_json(
            self._review_template.format(narration=narration),
            response_model=DramaturgeResponse,
        )

    async def _resolve_verdict(
        self,
        verdict: DramaturgeResponse,
        narration: str,
        context: dict,
    ) -> str:
        """Decide what to return based on the LLM verdict.

        Empty ``corrected_narration`` is treated as a bug signal rather
        than a silent passthrough — we log a warning and fall back so
        that prompt regressions or model misbehavior are debuggable
        after the fact. On a real correction we fan out entity
        escalation and log the contradiction descriptions for the
        admin dashboard.
        """
        corrected = (verdict.corrected_narration or "").strip()
        if not corrected:
            logger.warning(
                "Dramaturge returned empty corrected_narration "
                "(contradictions={0}, unknown_entities={1}); falling back",
                verdict.contradictions,
                verdict.unknown_entities,
            )
            return narration
        await self._escalate_unknowns(verdict, context)
        if verdict.contradictions:
            logger.info(
                "Dramaturge rewrote {0} contradiction(s): {1}",
                len(verdict.contradictions),
                verdict.contradictions,
            )
        return corrected

    async def _escalate_unknowns(
        self,
        verdict: DramaturgeResponse,
        context: dict,
    ) -> None:
        """Ask DataMiner to fill in any entities the verdict names.

        Reads ``verdict.unknown_entities`` (bare Wikipedia titles), not
        ``verdict.contradictions`` (which carries sentence-shaped fix
        descriptions and would never resolve as a lookup key).

        Preconditions (data_miner wired, non-empty cleaned entity
        list) are checked up-front so the defensive try-block around
        the actual escalation stays short and focused. The narration
        has already been corrected by the time we get here, so any
        exception inside escalation is strictly bookkeeping-for-next-
        turn and must never fail the current turn.
        ``CancelledError`` is re-raised so cooperative cancellation
        still works.
        """
        data_miner = context.get("data_miner")
        entities = _clean_entity_hints(verdict.unknown_entities)
        if data_miner is None or not entities:
            return
        try:
            await self._run_escalations(data_miner, entities, context["game_state"].knowledge_graph)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Dramaturge: entity escalation failed — narration already corrected")

    async def _run_escalations(
        self,
        data_miner: Any,
        entities: list[str],
        graph: KnowledgeGraph,
    ) -> None:
        """Fan out ``ensure_fact`` lookups concurrently.

        Each coroutine is wrapped in :meth:`_safe_ensure_fact` so a
        failure on one entity neither suppresses the others nor
        escapes to the caller. Per-coroutine try/except (rather than
        ``gather(return_exceptions=True)`` plus an isinstance walk)
        means ``logger.exception`` runs inside a real except block
        and preserves the traceback, and ``asyncio.CancelledError``
        propagates normally instead of being silently swallowed.
        """
        await asyncio.gather(
            *(self._safe_ensure_fact(data_miner, entity, graph) for entity in entities),
        )

    async def _safe_ensure_fact(
        self,
        data_miner: Any,
        entity: str,
        graph: KnowledgeGraph,
    ) -> None:
        """Call ``ensure_fact`` for one entity, log-and-swallow on failure."""
        try:
            await data_miner.ensure_fact(entity, graph=graph)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Dramaturge: ensure_fact escalation failed for {0!r}", entity)
