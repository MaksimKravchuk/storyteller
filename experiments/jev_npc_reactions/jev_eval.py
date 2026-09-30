"""A single fixed TypeSafe System One query for each reaction case."""

from __future__ import annotations

import json
import time
from types import MappingProxyType
from typing import Any
from urllib import request

from experiments.jev_npc_reactions.case_data import Case, jev_state

_JEV_MODEL = "jev-1.13.0"
_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
_TIMEOUT_SECONDS = 30

_CRITERIA: MappingProxyType[str, str] = MappingProxyType(
    {
        "attack": "Strike or use a weapon to injure the player immediately.",
        "restrain": "Physically stop, disarm, or arrest the player without trying to injure them.",
        "confront": "Challenge, question, warn, or negotiate with the player while staying in place.",
        "summon": "Call for help, guards, or allies while staying in the scene.",
        "withdraw": "Leave the immediate danger or flee.",
        "wait": "Do nothing material yet; observe the player.",
    }
)


def _build_request(case: Case, api_key: str) -> request.Request:
    payload = {
        "model": _JEV_MODEL,
        "state": jev_state(case),
        "questions": {
            "next_action": {
                "type": "choice",
                "instructions": (
                    "Which immediate action should this fictional NPC attempt in character? "
                    "Use the current situation and personality. Decide intent, not whether an action succeeds."
                ),
                "criteria": dict(_CRITERIA),
            }
        },
    }
    return request.Request(
        _ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )


def call_jev(case: Case, api_key: str) -> dict[str, Any]:
    """Return the decision distribution, model, usage, and latency."""
    start = time.perf_counter()
    with request.urlopen(_build_request(case, api_key), timeout=_TIMEOUT_SECONDS) as response:
        payload = json.load(response)
    return {
        "answer": payload["answers"]["next_action"],
        "model": payload["model"],
        "usage": payload["usage"],
        "latency_ms": round((time.perf_counter() - start) * 1000),
    }
