"""Cancellation triage in the concurrent NPC-turn path.

``_filter_successful`` triages the ``asyncio.gather(..., return_exceptions=True)``
results of the parallel NPC turns. ``asyncio.CancelledError`` inherits
from ``BaseException``, so an ``isinstance(outcome, BaseException)``
branch would swallow cooperative cancellation into a routine error log
line. It must re-raise instead.
"""

from __future__ import annotations

import asyncio
from typing import cast

import allure
import pytest

from cast import npc_turn as npc_turn_mod

pytestmark = [
    allure.epic("NPC Interaction"),
    allure.feature("NPC turn resolution"),
]


class _NpcStub:
    """Minimal NPC stand-in: ``_filter_successful`` only reads name/uuid."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.uuid = name


@allure.story("Error handling")
@allure.title("A cancelled NPC turn propagates out of _filter_successful instead of being logged")
def test_filter_successful_reraises_cancellation() -> None:
    eligible = [("uuid-a", _NpcStub("Alpha"), None)]

    with pytest.raises(asyncio.CancelledError):
        npc_turn_mod._filter_successful([asyncio.CancelledError()], eligible)


@allure.story("Error handling")
@allure.title("A routine NPC-turn exception is logged and skipped while survivors are kept")
def test_filter_successful_keeps_survivors_and_skips_failures() -> None:
    good = cast(npc_turn_mod.NPCAction, object())
    eligible = [("uuid-a", _NpcStub("Alpha"), None), ("uuid-b", _NpcStub("Beta"), None)]

    kept = npc_turn_mod._filter_successful([RuntimeError("LLM timeout"), good], eligible)

    assert kept == [good]
