"""Scenario execution internals: engine prep, turn driving, scoring."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from benchmarks.harness import (
    _reliability_capture as reliability_capture,
    _temperature_override as temperature_override,
)
from benchmarks.harness.scoring import score_scenario
from benchmarks.harness.snapshots import snapshot
from benchmarks.harness.transcript import NarratorCapture
from benchmarks.harness.types._captures import CapturedTurn
from engine.factory import create_engine

if TYPE_CHECKING:
    from benchmarks.harness.types import _scenarios, _scores

    Scenario = _scenarios.Scenario
    ScenarioState = _scenarios.ScenarioState
    ElementScore = _scores.ElementScore
    PanelMember = _scores.PanelMember


@dataclass(frozen=True)
class _ExecutionResult:
    """Internal container for one scenario execution's scored output."""

    element_scores: list[ElementScore]
    captured_turns: list[CapturedTurn]
    started_at: str
    duration_seconds: float
    reliability_counts: dict[str, dict[str, int]]


async def _prepare_engine(
    cfg: Any,
    scenario_state: ScenarioState,
) -> tuple[Any, NarratorCapture]:
    """Restore the engine from the seeded state and install the capture hook.

    Reads ``BENCHMARK_TEMPERATURE_OVERRIDE`` / ``BENCHMARK_<ROLE>_TEMPERATURE``
    env vars and pins engine LLM temperatures when set. Production callers never
    set these vars, so the override is harness-scoped.
    """
    # Benchmarks score narration on curated, deterministic scenarios. The
    # content-safety moderator would reject some scripted player actions (e.g.
    # combat premises) and is irrelevant to narration scoring, so it is disabled
    # for the harness — measure narration, not moderation.
    cfg = cfg.model_copy(update={"safety_enabled": False})
    engine = create_engine(
        cfg,
        temperature_override=temperature_override.load_temperature_overrides(),
    )
    await engine.restore_session(
        scenario_state.game_state,
        scenario_state.game_state.knowledge_graph,
        scenario_state.events,
    )
    capture = NarratorCapture()
    capture.attach(engine)
    return engine, capture


async def _capture_single_turn(
    engine: Any,
    capture: NarratorCapture,
    turn_index: int,
    script_turn: Any,
) -> CapturedTurn:
    """Drive one scripted action through the engine and package the output."""
    turn_start = time.monotonic()
    action = script_turn.player_action
    narration = await engine.process_action(action)
    turn_outputs = capture.pop_next()
    duration_ms = int((time.monotonic() - turn_start) * 1000)
    return CapturedTurn(
        index=turn_index,
        player_action=action,
        narration=narration,
        turn_outputs=turn_outputs,
        duration_ms=duration_ms,
    )


async def _drive_turns(
    engine: Any,
    capture: NarratorCapture,
    scenario: Scenario,
    scenario_state: ScenarioState,
) -> tuple[list[CapturedTurn], list[Any]]:
    """Walk the script turn-by-turn, capturing narration + snapshots."""
    snapshots: list[Any] = [snapshot(scenario_state.game_state)]
    captured_turns: list[CapturedTurn] = []
    # while+pop avoids await inside a for-header (WPS476).
    pending: list[tuple[int, Any]] = list(enumerate(scenario.script))
    while pending:
        turn_index, script_turn = pending.pop(0)
        captured_turns.append(await _capture_single_turn(engine, capture, turn_index, script_turn))
        snapshots.append(snapshot(scenario_state.game_state))
    return captured_turns, snapshots


async def _score_bundle(
    scenario: Scenario,
    cfg: Any,
    panel_members: list[PanelMember],
    turns: list[CapturedTurn],
    snapshots: list[Any],
) -> list[ElementScore]:
    """Run :func:`score_scenario` and return only the element scores."""
    return await score_scenario(
        scenario.elements,
        turns,
        snapshots,
        panel=panel_members,
        cfg=cfg,
    )


async def _run_script(
    scenario: Scenario,
    cfg: Any,
) -> tuple[list[CapturedTurn], list[Any]]:
    """Build the engine, restore state, drive every scripted turn.

    Resets the reliability counters before the script runs so the
    snapshot captured by :func:`execute_scenario` reflects only this
    scenario's silent fallbacks and validation retries.
    """
    reliability_capture.reset_for_scenario()
    scenario_state = scenario.build_state()
    engine, capture = await _prepare_engine(cfg, scenario_state)
    return await _drive_turns(engine, capture, scenario, scenario_state)


async def execute_scenario(
    scenario: Scenario,
    cfg: Any,
    panel_members: list[PanelMember],
) -> _ExecutionResult:
    """Build the engine, drive the script, score the elements."""
    started_at = datetime.now(timezone.utc).isoformat()
    run_start = time.monotonic()
    turns, snapshots = await _run_script(scenario, cfg)
    scores = await _score_bundle(scenario, cfg, panel_members, turns, snapshots)
    return _ExecutionResult(
        element_scores=scores,
        captured_turns=turns,
        started_at=started_at,
        duration_seconds=time.monotonic() - run_start,
        reliability_counts=reliability_capture.collect_reliability_counts(),
    )
