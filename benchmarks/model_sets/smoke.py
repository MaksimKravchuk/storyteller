"""Connectivity smoke test for the non-baseline model sets.

Hits each OpenRouter model in the three alternate sets with a tiny
ping so that we fail fast if the key is missing, a model id has been
deprecated, or a route is unavailable — before committing to the full
benchmark suite.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

from config import Config, get_api_key_for_provider, load_config
from defaults.models import AI_MODELS, ModelConfig
from llm.factory import create_llm_client
from llm.message import Message, Role

_PING = "Reply with the single word OK."
_PROBE_MAX_TOKENS = 8
_EXIT_OK = 0
_EXIT_PROBE_FAILURES = 1
_EXIT_MISSING_KEY = 2
_DETAIL_CLIP = 160
_REPLY_CLIP = 80


@dataclass(frozen=True)
class _Probe:
    label: str
    model: ModelConfig


@dataclass(frozen=True)
class _ProbeResult:
    label: str
    ok: bool
    detail: str


_PROBES: tuple[_Probe, ...] = (
    _Probe("max-director", AI_MODELS.gpt5_4),
    _Probe("max-agent", AI_MODELS.gemini_pro),
    _Probe("max-narrator", AI_MODELS.claude_sonnet),
    _Probe("optimal-director", AI_MODELS.gpt5_4_mini),
    _Probe("optimal-agent", AI_MODELS.deepseek_chat),
    _Probe("optimal-narrator", AI_MODELS.deepseek_v4_pro),
    _Probe("economy-director", AI_MODELS.gpt5_4_nano),
    _Probe("economy-agent", AI_MODELS.deepseek_chat),
    _Probe("economy-narrator", AI_MODELS.gemini_flash),
)


def _format_exc(exc: Exception) -> str:
    return "{0}: {1}".format(type(exc).__name__, str(exc)[:_DETAIL_CLIP])


async def _probe_one(probe: _Probe, cfg: Config) -> _ProbeResult:
    api_key = get_api_key_for_provider(probe.model.provider, cfg)
    client = create_llm_client(probe.model, api_key=api_key)
    messages = [Message(role=Role.USER, body=_PING)]
    try:
        response = await client.send_message(messages, max_tokens=_PROBE_MAX_TOKENS)
    except Exception as exc:
        return _ProbeResult(probe.label, False, _format_exc(exc))
    reply = (response.body or "").strip()[:_REPLY_CLIP]
    return _ProbeResult(probe.label, True, reply)


def _emit(outcome: _ProbeResult) -> None:
    status = "OK  " if outcome.ok else "FAIL"
    sys.stdout.write("  [{0}] {1:<24} {2}\n".format(status, outcome.label, outcome.detail))


async def _run() -> int:
    cfg = load_config()
    if not cfg.openrouter_api_key:
        sys.stderr.write("OPENROUTER_API_KEY is not configured — aborting smoke test.\n")
        return _EXIT_MISSING_KEY
    outcomes = await asyncio.gather(*(_probe_one(probe, cfg) for probe in _PROBES))
    all_ok = all(outcome.ok for outcome in outcomes)
    for outcome in outcomes:
        _emit(outcome)
    return _EXIT_OK if all_ok else _EXIT_PROBE_FAILURES


if __name__ == "__main__":
    sys.exit(asyncio.run(_run()))
