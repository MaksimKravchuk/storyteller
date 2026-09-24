"""Existing Actor dialogue calls for the Jev reaction comparison."""

from __future__ import annotations

import time
from contextlib import aclosing
from dataclasses import dataclass
from typing import Any

from cast.actor import Actor
from experiments.jev_dialogue_reactions.case_data import Case, make_state
from knowledge.query import KnowledgeQueryEngine
from llm.message import LLMResponse
from llm.openai_client import OpenAIClient
from models.game_state import GameState
from models.npc_card import NPCCard

_ACTOR_MODEL = "gpt-5.4-nano"
_KEY_CHOICE = "choice"
_KEY_MODEL = "model"

_REMINDER_EN = (
    "Before replying, check what you can know from your background and memories. "
    "A new term may be known, partly inferred, or unknown. Distinguish surprise "
    "from credible fear. A player's explanation is a claim, not proof."
)
_REMINDER_RU = (
    "Прежде чем ответить, учитывай только свой опыт и воспоминания. "
    "Новое слово может быть знакомым, понятным лишь отчасти или неизвестным. "
    "Отличай удивление от страха перед реальной угрозой. Объяснение игрока — утверждение, а не доказательство."
)


class RecordingClient:
    """Capture the Actor response and usage while using its normal provider path."""

    def __init__(self, api_key: str) -> None:
        self.model = _ACTOR_MODEL
        self._delegate = OpenAIClient(model=_ACTOR_MODEL, api_key=api_key)
        self.response: LLMResponse | None = None

    async def send_message(self, **kwargs: Any) -> LLMResponse:
        """Forward the normal Actor call and retain its response."""
        self.response = await self._delegate.send_message(**kwargs)
        return self.response

    async def aclose(self) -> None:
        """Close the underlying HTTP client before its event loop ends."""
        await self._delegate._client.close()


@dataclass
class _ActorTrial:
    actor: Actor
    state: GameState
    npc: NPCCard
    client: RecordingClient


def _prepare_actor(case: Case, api_key: str) -> _ActorTrial:
    state, npc = make_state(case)
    client = RecordingClient(api_key)
    actor = Actor(
        llm_client=client,
        npc=npc,
        knowledge_query=KnowledgeQueryEngine(state.knowledge_graph),
        language=case.language,
    )
    return _ActorTrial(actor=actor, state=state, npc=npc, client=client)


def _reminder(case: Case) -> str:
    return _REMINDER_RU if case.language == "Russian" else _REMINDER_EN


def actor_input(case: Case, variant: str, jev: dict[str, Any] | None = None) -> str:
    """Keep scene and player action identical across the three arms."""
    base = "Player is addressing you.\nCurrent scene: {0}\nPlayer action: {1}".format(
        case.scene,
        case.player_action,
    )
    if variant == "baseline":
        return base
    if variant == "reminder":
        return "{0}\n{1}".format(base, _reminder(case))
    if variant != "jev" or jev is None:
        raise ValueError("Jev variant requires a decision")
    answers = jev["answers"]
    cue = "understanding={0}; outward_reaction={1}".format(
        answers["understanding"][_KEY_CHOICE],
        answers["expression"][_KEY_CHOICE],
    )
    if case.language == "Russian":
        guidance = (
            "Подсказка для этого хода (не новый факт): {0}. "
            "Вырази её своими словами, если она согласуется с опытом. "
            "Это краткая реакция, не меняй поле mood только из-за подсказки."
        ).format(cue)
    else:
        guidance = (
            "Cue for this turn (not a new fact): {0}. "
            "Express it in your own words if your experience supports it. "
            "This is a brief reaction; do not change the mood field from this cue alone."
        ).format(cue)
    return "{0}\n{1}".format(actor_input(case, "reminder"), guidance)


def _actor_result(trial: _ActorTrial, text: str, started: float) -> dict[str, Any]:
    response = trial.client.response
    if response is None:
        raise RuntimeError("Actor returned without a provider response")
    return {
        "text": text,
        "raw": response.body,
        _KEY_MODEL: response.model or trial.client.model,
        "usage": response.usage,
        "mood_after": trial.npc.current_mood,
        "latency_ms": round((time.perf_counter() - started) * 1000),
    }


async def call_actor(
    case: Case,
    variant: str,
    api_key: str,
    jev: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the real dialogue Actor with fresh state and the selected input arm."""
    trial = _prepare_actor(case, api_key)
    started = time.perf_counter()
    async with aclosing(trial.client):
        reply = await trial.actor.execute(
            actor_input(case, variant, jev),
            context={"game_state": trial.state, "location_name": "{0}, {1}".format(case.location, case.era)},
        )
        return _actor_result(trial, reply.text, started)
