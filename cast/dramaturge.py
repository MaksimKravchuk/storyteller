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
from knowledge.graph_queries import query_by_canon
from knowledge.node import CanonSource, KnowledgeNode
from loguru import logger
from models.game_state import GameState
from prompts.dramaturge_prompts import DRAMATURGE_REVIEW, DRAMATURGE_SYSTEM

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
    historical: list[KnowledgeNode] = query_by_canon(graph, CanonSource.HISTORICAL)
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
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=DRAMATURGE_SYSTEM,
        )
        self._language = language

    async def act(self, input_data: str, context: dict) -> str:
        """Review ``input_data`` and return a consistency-checked narration.

        ``input_data``: The raw narration string produced by the Narrator.

        ``context``: Must contain ``game_state``. Optionally accepts
        ``data_miner`` — when provided, the Dramaturge calls its
        ``ensure_fact`` method as a side channel for any contradiction
        the LLM surfaces that looks like an unknown-entity escalation,
        so future turns have the fact on hand.

        Returns the corrected narration string. On any Dramaturge error
        we log and fall back to the original narration — the player
        must never see a half-rewritten passage.
        """
        narration = (input_data or "").strip()
        if not narration:
            return narration

        game_state: GameState = context["game_state"]
        self.set_context(
            setting_name=game_state.setting.name,
            time_period=game_state.setting.time_period,
            historical_facts=_format_historical_facts(game_state.knowledge_graph),
            scene_history=_format_scene_history(game_state.scene_conversation_log),
            language=self._language,
        )

        try:
            verdict = await self._send_json(
                DRAMATURGE_REVIEW.render(narration=narration),
                response_model=DramaturgeResponse,
            )
        except (ValueError, RuntimeError) as exc:
            logger.warning(
                "Dramaturge review failed ({0}); falling back to original narration",
                type(exc).__name__,
            )
            return narration

        corrected = (verdict.corrected_narration or "").strip()
        if not corrected:
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

        The Dramaturge itself is strictly read-only on the knowledge
        graph. When a contradiction hint mentions an unknown entity,
        we delegate the Wikipedia lookup to ``DataMiner.ensure_fact``
        so the fact becomes available on subsequent turns. Failures
        here are never fatal — the narration is already corrected.
        """
        data_miner = context.get("data_miner")
        if data_miner is None or not verdict.contradictions:
            return
        entities = _clean_entity_hints(verdict.contradictions)
        if not entities:
            return
        graph: KnowledgeGraph = context["game_state"].knowledge_graph
        await self._run_escalations(data_miner, entities, graph)

    async def _run_escalations(
        self,
        data_miner: Any,
        entities: list[str],
        graph: KnowledgeGraph,
    ) -> None:
        """Fan out concurrent ``ensure_fact`` calls and log individual failures.

        Lookups run concurrently because they are independent Wikipedia
        round-trips. ``return_exceptions=True`` keeps one broken entity
        from suppressing the others — we walk the results and log any
        exception at warning level, never bubbling.
        """
        outcomes = await asyncio.gather(
            *(data_miner.ensure_fact(entity, graph=graph) for entity in entities),
            return_exceptions=True,
        )
        for entity, outcome in zip(entities, outcomes):
            if isinstance(outcome, Exception):
                logger.warning(
                    "Dramaturge: ensure_fact escalation failed for {0!r}: {1}",
                    entity,
                    outcome,
                )
