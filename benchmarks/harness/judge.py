"""Evidence-citing LLM judges for benchmark scoring.

Each judge model answers a narrow yes/no question against captured turn
text and is required to cite a verbatim quote. Quotes are normalised
(lowercase, whitespace collapsed) and checked as substrings of the
original material; hallucinated quotes flip a vote to NO regardless of
the stated verdict. This is what lets us treat a 6-model panel as a
reliable witness majority instead of a vibes average.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from benchmarks.harness._judge_vote import (
    _build_vote_from_payload,
    _error_vote,
    _parse_vote_payload,
)
from benchmarks.harness.types._elements import EvidencePromptSpec
from benchmarks.harness.types._scores import JudgeVote, PanelMember
from config import Config, get_api_key_for_provider
from defaults.models import ModelConfig
from llm.factory import create_llm_client
from llm.message import Message, Role

_JUDGE_MAX_TOKENS = 400
_JUDGE_TEMPERATURE: float = float(0)

_SYSTEM_PROMPT = (
    "You are one of several independent witnesses evaluating a text-quest game transcript. "
    "Answer the yes/no question using ONLY the provided TURN TEXT. "
    "Do NOT invent, paraphrase, or embellish. "
    "Respond with a single JSON object on one line containing EXACTLY these fields:\n"
    '{"verdict": "YES" | "NO", "reasoning": "<one short sentence>", "quote": "<verbatim substring from TURN TEXT>"}\n'
    "Rules:\n"
    "- quote must be an EXACT substring of TURN TEXT (no paraphrasing, no ellipses).\n"
    '- If no supporting quote exists, return verdict NO and quote "".\n'
    "- Output JSON only — no markdown fences, no commentary outside the object."
)

_USER_TEMPLATE = (
    "SCENARIO BRIEF:\n{brief}\n\nQUESTION:\n{question}\n\nTURN TEXT:\n{turn_text}\n\nReply with the JSON object only."
)


@dataclass(frozen=True)
class JudgeCall:
    """One judge x one element dispatch."""

    spec: EvidencePromptSpec
    turn_text: str


def _elapsed_ms(start: float) -> int:
    """Return monotonic-clock elapsed milliseconds since ``start``."""
    return int((time.monotonic() - start) * 1000)


async def _send_judge_prompt(
    member: PanelMember,
    call: JudgeCall,
    cfg: Config,
    temperature: float,
) -> str:
    """Invoke the judge LLM and return its raw response body."""
    model_config = ModelConfig(
        provider=member.provider,
        model_id=member.model_id,
        temperature=temperature,
        max_tokens=_JUDGE_MAX_TOKENS,
    )
    client = create_llm_client(model_config, api_key=get_api_key_for_provider(member.provider, cfg))
    user_body = _USER_TEMPLATE.format(
        brief=call.spec.scenario_brief,
        question=call.spec.question,
        turn_text=call.turn_text,
    )
    response = await client.send_message(
        messages=[Message(role=Role.USER, body=user_body)],
        system_prompt=_SYSTEM_PROMPT,
        response_format={"type": "json_object"},
        temperature=temperature,
        max_tokens=_JUDGE_MAX_TOKENS,
    )
    return response.body


async def run_judge(
    member: PanelMember,
    call: JudgeCall,
    *,
    cfg: Config,
    temperature: float = _JUDGE_TEMPERATURE,
) -> JudgeVote:
    """Dispatch one judge call and return its vote.

    Errors (network, decode, missing quote field) surface as an
    ``ERROR`` vote with the exception text so aggregate scoring can
    treat them as abstentions rather than crashing the whole run.
    """
    start = time.monotonic()
    try:
        body = await _send_judge_prompt(member, call, cfg, temperature)
    except Exception as exc:
        return _error_vote(member, _elapsed_ms(start), str(exc))
    latency_ms = _elapsed_ms(start)
    try:
        payload = _parse_vote_payload(body)
    except (ValueError, json.JSONDecodeError) as exc:
        return _error_vote(member, latency_ms, "parse error: {0}".format(exc))
    return _build_vote_from_payload(
        member.model_id,
        member.provider,
        payload,
        call.turn_text,
        latency_ms,
    )
