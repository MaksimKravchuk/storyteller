"""Two typed TypeSafe System One judgments about a dialogue situation."""

from __future__ import annotations

import json
import time
from types import MappingProxyType
from typing import Any
from urllib import request

from experiments.jev_dialogue_reactions.case_data import Case, jev_state

_JEV_MODEL = "jev-1.13.0"
_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
_TIMEOUT_SECONDS = 30

_UNDERSTANDING: MappingProxyType[str, str] = MappingProxyType(
    {
        "known": "The NPC can identify the referent from their own established experience or knowledge.",
        "partial": "The NPC can infer a rough category or recall a claim about it, but not its mechanism or truth.",
        "unknown": "The NPC cannot identify the referent; they can still describe what they observe or ask questions.",
    }
)
_EXPRESSION: MappingProxyType[str, str] = MappingProxyType(
    {
        "ordinary": "An unremarkable request; no surprise or unusual alarm.",
        "curious": "Interested in learning more, without a threat response.",
        "startled": "Momentarily surprised by a concrete unexpected observation.",
        "wary": "Cautious because the observed situation may be risky or deceptive.",
        "afraid": "Perceives a credible immediate danger and shows fear.",
        "skeptical": "Doubts an extraordinary claim without treating it as proven or dangerous.",
    }
)


def _jev_request(case: Case, api_key: str) -> request.Request:
    payload = {
        "model": _JEV_MODEL,
        "state": jev_state(case),
        "questions": {
            "understanding": {
                "type": "choice",
                "instructions": (
                    "How much can THIS NPC understand about the referent of the player's words or shown object? "
                    "Use only this NPC's era, biography, observation, and held memory. "
                    "The player's explanation is a claim, not an established fact."
                ),
                "criteria": dict(_UNDERSTANDING),
            },
            "expression": {
                "type": "choice",
                "instructions": (
                    "What is THIS NPC's most plausible immediate outward reaction to the current player action? "
                    "This is an ephemeral expression, not a persistent mood or combat decision. "
                    "Mere unfamiliar vocabulary is not a danger; fear requires perceived credible danger."
                ),
                "criteria": dict(_EXPRESSION),
            },
        },
    }
    return request.Request(
        _ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )


def call_jev(case: Case, api_key: str) -> dict[str, Any]:
    """Return two typed judgments without storing any credential."""
    started = time.perf_counter()
    with request.urlopen(_jev_request(case, api_key), timeout=_TIMEOUT_SECONDS) as response:
        payload = json.load(response)
    return {
        "answers": payload["answers"],
        "model": payload["model"],
        "usage": payload["usage"],
        "latency_ms": round((time.perf_counter() - started) * 1000),
    }
