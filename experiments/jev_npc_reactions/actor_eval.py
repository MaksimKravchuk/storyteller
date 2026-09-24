"""Call Storyteller's existing Actor on the same fictional situation."""

from __future__ import annotations

import time
from typing import Any

from cast.actor import Actor
from cast.npc_turn import _build_turn_prompt
from experiments.jev_npc_reactions.case_data import Case, make_state
from knowledge.query import KnowledgeQueryEngine
from llm.openai_client import OpenAIClient

_ACTOR_MODEL = "gpt-5.4-nano"


async def call_actor(case: Case, api_key: str) -> dict[str, Any]:
    """Return the real Actor's raw action JSON and latency."""
    state, npc = make_state(case)
    actor = Actor(
        llm_client=OpenAIClient(model=_ACTOR_MODEL, api_key=api_key),
        npc=npc,
        knowledge_query=KnowledgeQueryEngine(state.knowledge_graph),
        language=case.language,
    )
    start = time.perf_counter()
    reply = await actor.execute(
        _build_turn_prompt(npc, case.player_action, state),
        context={"is_npc_turn": True, "game_state": state},
    )
    return {
        "text": reply.text,
        "model": _ACTOR_MODEL,
        "latency_ms": round((time.perf_counter() - start) * 1000),
    }
