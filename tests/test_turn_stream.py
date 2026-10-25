"""Tests for the live turn stream: event channel, sentence moderation gate, engine wiring."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock

import allure
import pytest

from engine.game_engine import GameEngine
from engine.moderation import SentenceGate, moderate_narration
from llm import turn_stream
from safety.moderator import Moderator
from safety.result import ModerationCategory, ModerationSeverity
from tests._turn_stream_helpers import HeldProvider, RecordingSink, bounded, settle

pytestmark = [
    allure.epic("Narrative Delivery"),
    allure.feature("Live turn stream"),
]


@dataclass
class _FlagSubstringProvider:
    """Moderation provider flagging any text containing ``needle``; records what it saw."""

    needle: str = "\0"
    name: str = "flag-substring"
    seen: list[str] = field(default_factory=list)

    async def score(self, text: str) -> Mapping[ModerationCategory, ModerationSeverity]:
        self.seen.append(text)
        return {ModerationCategory.HATE: ModerationSeverity.HIGH} if self.needle in text else {}


async def _emit(text: str) -> None:
    handler = turn_stream.delta_handler()
    assert handler is not None
    await handler(text)


async def _narrate_with_hit() -> str:
    await _emit("Fine. ")
    await _emit("A slur. ")
    return "Fine. A slur."


async def _narrate_then_fail() -> str:
    await _emit("Half a passage. ")
    raise RuntimeError("narrator down")


async def _director_execute(_: str) -> str:
    await turn_stream.emit_stage("acting")
    await _emit("Rain falls.")
    return "Rain falls."


@allure.story("Event channel")
@allure.title("Stage and delta emits are no-ops when no sink is bound")
@pytest.mark.asyncio
async def test_emits_without_sink_are_noops() -> None:
    await turn_stream.emit_stage("acting")
    assert turn_stream.delta_handler() is None
    assert turn_stream.current_sink() is None


@allure.story("Event channel")
@allure.title("A bound sink receives stages; muted(True) hides it and muted(False) keeps it")
@pytest.mark.asyncio
async def test_bound_and_muted_sink() -> None:
    sink = RecordingSink()
    with turn_stream.bound(sink):
        await turn_stream.emit_stage("acting")
        with turn_stream.muted(True):
            await turn_stream.emit_stage("hidden")
        with turn_stream.muted(False):
            await turn_stream.emit_stage("narrating")
    await turn_stream.emit_stage("after")
    assert sink.stages == ["acting", "narrating"]


@allure.story("Sentence gate")
@allure.title("Without a moderator the gate forwards deltas unchanged and immediately")
@pytest.mark.asyncio
async def test_gate_passthrough_without_moderator() -> None:
    sink = RecordingSink()
    gate = SentenceGate(None, sink)
    await gate.delta("Hel")
    await gate.delta("lo")
    await gate.flush()
    assert sink.deltas == ["Hel", "lo"]


@allure.story("Sentence gate")
@allure.title("With a moderator the gate releases only checked, completed sentences, then the tail on flush")
@pytest.mark.asyncio
async def test_gate_releases_checked_sentences() -> None:
    provider = _FlagSubstringProvider()
    sink = RecordingSink()
    gate = SentenceGate(Moderator(providers=[provider]), sink)
    await gate.delta("The door creaks. A gu")
    await gate.delta("ard «waits.» Then")
    await gate.flush()
    assert sink.deltas == ["The door creaks. ", "A guard «waits.» ", "Then"]
    assert provider.seen == sink.deltas


@allure.story("Sentence gate")
@allure.title("Sentence checks run while the Narrator keeps streaming; release still waits for each check, in order")
@pytest.mark.asyncio
async def test_gate_pipelines_checks() -> None:
    provider = HeldProvider()
    sink = RecordingSink()
    gate = SentenceGate(Moderator(providers=[provider]), sink)
    await bounded(gate.delta("One. "))
    await bounded(gate.delta("Two. "))
    await settle()
    assert provider.seen == ["One. ", "Two. "]
    assert sink.deltas == []
    provider.release.set()
    await gate.flush()
    assert sink.deltas == ["One. ", "Two. "]


@allure.story("Sentence gate")
@allure.title("A flagged sentence is never released and stops everything after it")
@pytest.mark.asyncio
async def test_gate_blocks_after_flagged_sentence() -> None:
    sink = RecordingSink()
    gate = SentenceGate(Moderator(providers=[_FlagSubstringProvider(needle="slur")]), sink)
    await gate.delta("Calm start. A slur here. ")
    await gate.delta("More text. ")
    await gate.flush()
    assert sink.deltas == []
    assert gate.blocked is not None


@allure.story("Engine wiring")
@allure.title("moderate_narration drops queued sentences when the Narrator fails mid-stream")
@pytest.mark.asyncio
async def test_moderate_narration_cancels_gate_on_failure() -> None:
    sink = RecordingSink()
    with turn_stream.bound(sink), pytest.raises(RuntimeError):
        await moderate_narration(Moderator(providers=[_FlagSubstringProvider()]), _narrate_then_fail)
    await settle()
    assert sink.deltas == []


@allure.story("Engine wiring")
@allure.title("moderate_narration replaces the whole passage when a streamed sentence is flagged")
@pytest.mark.asyncio
async def test_moderate_narration_falls_back_on_streamed_hit() -> None:
    moderator = Moderator(providers=[_FlagSubstringProvider(needle="slur")])
    sink = RecordingSink()

    with turn_stream.bound(sink):
        narration = await moderate_narration(moderator, _narrate_with_hit)

    assert sink.deltas == ["Fine. "]
    assert "slur" not in narration


@allure.story("Engine wiring")
@allure.title("process_action inside a bound stream forwards stage events through the moderation gate")
@pytest.mark.asyncio
async def test_process_action_streams_through_gate() -> None:
    engine = GameEngine(moderator=None)
    director = MagicMock()
    director.execute = AsyncMock(side_effect=_director_execute)
    engine._director = director
    sink = RecordingSink()

    with turn_stream.bound(sink):
        narration = await engine.process_action("wait")

    assert narration == "Rain falls."
    assert sink.stages == ["acting"]
    assert sink.deltas == ["Rain falls."]
