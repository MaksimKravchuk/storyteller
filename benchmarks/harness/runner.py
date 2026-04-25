"""End-to-end scenario runner — builds the engine, drives turns, scores."""

from __future__ import annotations

from dataclasses import dataclass

from benchmarks.harness._run_execution import _ExecutionResult, execute_scenario
from benchmarks.harness.panel import DEFAULT_MAX_JUDGES, PanelAssembly, assemble_panel
from benchmarks.harness.types._scenarios import Scenario
from benchmarks.harness.types._scores import ScenarioReport
from config import Config


@dataclass(frozen=True)
class RunOptions:
    """Knobs for one :func:`run_scenario_once` invocation."""

    cfg: Config
    iteration: int = 0
    panel_overrides: list[str] | None = None
    max_judges: int | None = None
    engine_git_sha: str = ""


async def run_scenario_once(scenario: Scenario, *, options: RunOptions) -> ScenarioReport:
    """Run one iteration of ``scenario`` and return a scored report."""
    assembly = assemble_panel(
        options.cfg,
        overrides=options.panel_overrides,
        max_judges=_resolve_max_judges(options.max_judges),
    )
    execution = await execute_scenario(scenario, options.cfg, assembly.members)
    return _build_report(scenario, execution, assembly, options)


def _resolve_max_judges(configured: int | None) -> int:
    """Return the effective judge cap, falling back to the roster default."""
    if configured is None:
        return DEFAULT_MAX_JUDGES
    return configured


def _engine_model_summary(cfg: Config) -> dict[str, str]:
    """Capture the engine's per-role model ids for the reproducibility header."""
    return {
        "director_model": cfg.director_model,
        "agent_model": cfg.agent_model,
        "narrator_model": cfg.narrator_model,
        "dramaturge_model": cfg.dramaturge_model,
        "dramaturge_enabled": str(cfg.dramaturge_enabled).lower(),
    }


def _build_report(
    scenario: Scenario,
    execution: _ExecutionResult,
    assembly: PanelAssembly,
    options: RunOptions,
) -> ScenarioReport:
    """Compose the final :class:`ScenarioReport` from run artefacts."""
    return ScenarioReport(
        scenario_id=scenario.id,
        scenario_label=scenario.label,
        iteration=options.iteration,
        total_base=sum(score.base_value for score in execution.element_scores),
        total_awarded=sum(score.awarded for score in execution.element_scores),
        element_scores=execution.element_scores,
        captured_turns=execution.captured_turns,
        panel=list(assembly.members),
        skipped_panel_candidates=list(assembly.skipped),
        engine_git_sha=options.engine_git_sha,
        engine_models=_engine_model_summary(options.cfg),
        started_at=execution.started_at,
        duration_seconds=execution.duration_seconds,
    )
