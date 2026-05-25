"""Evidence-citing LLM judges for benchmark scoring."""

from __future__ import annotations

import time
from dataclasses import dataclass

from loguru import logger

from benchmarks.harness._judge_vote import (
    _build_vote_from_payload,
    _error_vote,
    _parse_vote_payload,
)
from benchmarks.harness.types._elements import EvidencePromptSpec
from benchmarks.harness.types._scores import JudgeVote, PanelMember
from cast._reliability_metrics import record_judge_error
from config import Config, get_api_key_for_provider
from defaults.models import ModelConfig
from llm.factory import create_llm_client
from llm.message import Message, OutputFormat, Role

_JUDGE_MAX_TOKENS = 400
_JUDGE_TEMPERATURE: float = float(0)
_JSON_REMINDER = "\n\nReply in valid JSON only."

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
    user_suffix: str = "",
) -> str:
    """Invoke the judge LLM and return its raw response body."""
    model_config = ModelConfig(
        provider=member.provider,
        model_id=member.model_id,
        temperature=temperature,
        max_tokens=_JUDGE_MAX_TOKENS,
    )
    client = create_llm_client(model_config, api_key=get_api_key_for_provider(member.provider, cfg))
    user_body = (
        _USER_TEMPLATE.format(
            brief=call.spec.scenario_brief,
            question=call.spec.question,
            turn_text=call.turn_text,
        )
        + user_suffix
    )
    response = await client.send_message(
        messages=[Message(role=Role.USER, body=user_body)],
        system_prompt=_SYSTEM_PROMPT,
        output_format=OutputFormat(response_format={"type": "json_object"}),
        temperature=temperature,
        max_tokens=_JUDGE_MAX_TOKENS,
    )
    return response.body


def _log_judge_failure(member: PanelMember, stage: str, exc: BaseException | None) -> None:
    """Emit a warning log identifying which judge failed and why."""
    logger.warning(
        "Benchmark judge {provider}/{model} failed during {stage}: {err_type}: {err}",
        provider=member.provider,
        model=member.model_id,
        stage=stage,
        err_type=type(exc).__name__,
        err=str(exc),
    )


def _try_parse_body(body: str) -> tuple[dict | None, Exception | None]:
    """Return ``(payload, None)`` on success or ``(None, exc)`` on any parse failure."""
    try:
        return _parse_vote_payload(body), None
    except ValueError as exc:
        return None, exc


async def _resample_once(
    member: PanelMember,
    call: JudgeCall,
    cfg: Config,
    temperature: float,
    start: float,
) -> tuple[dict | None, JudgeVote | None]:
    """Retry the judge prompt once; return ``(payload, None)`` on success or ``(None, error_vote)``."""
    try:
        retry_body = await _send_judge_prompt(member, call, cfg, temperature, user_suffix=_JSON_REMINDER)
    except Exception as send_exc:
        _log_judge_failure(member, "retry-send", send_exc)
        return None, _error_vote(member, _elapsed_ms(start), "parse error: unparseable judge response")
    payload, parse_exc = _try_parse_body(retry_body)
    if payload is None:
        _log_judge_failure(member, "retry-parse", parse_exc)
        record_judge_error(member.model_id, 2)
        return None, _error_vote(member, _elapsed_ms(start), "parse error: unparseable judge response on retry")
    return payload, None


async def run_judge(
    member: PanelMember,
    call: JudgeCall,
    *,
    cfg: Config,
    temperature: float = _JUDGE_TEMPERATURE,
) -> JudgeVote:
    """Dispatch one judge call and return its vote.

    On a JSON-parse failure the prompt is retried once with a reminder
    appended. ERROR is returned only when both attempts fail.
    """
    start = time.monotonic()
    try:
        body = await _send_judge_prompt(member, call, cfg, temperature)
    except Exception as send_exc:
        _log_judge_failure(member, "send", send_exc)
        return _error_vote(member, _elapsed_ms(start), "send error: {0}".format(send_exc))
    payload, parse_exc = _try_parse_body(body)
    if payload is None:
        _log_judge_failure(member, "parse", parse_exc)
        record_judge_error(member.model_id, 1)
        payload, error_vote = await _resample_once(member, call, cfg, temperature, start)
        if error_vote is not None:
            return error_vote
    assert payload is not None
    return _build_vote_from_payload(
        member.model_id,
        member.provider,
        payload,
        call.turn_text,
        _elapsed_ms(start),
    )
