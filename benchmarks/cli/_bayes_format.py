"""Text formatting for the Bayesian benchmark-comparison verdicts."""

from __future__ import annotations

from benchmarks.harness.bayes._types import (
    ElementInferiority,
    PortfolioVerdict,
    ScenarioVerdict,
)

_LABEL_COL_WIDTH = 44
_NOTABLE_THRESHOLD = 0.7  # surface elements whose move clears this confidence

_SCENARIO_LINE = (
    "[bayes] {sid}: Δ={mean:+.2f} [95% CI {lo:+.2f}, {hi:+.2f}]  P(reg)={reg:.2f} P(eq)={eq:.2f} P(imp)={imp:.2f}"
)
_PORTFOLIO_LINE = (
    "[bayes] PORTFOLIO ({count} scenarios): ΣΔ={mean:+.2f} [95% CI {lo:+.2f}, {hi:+.2f}]  "
    "P(suite worse)={reg:.2f} P(eq)={eq:.2f} P(suite better)={imp:.2f}"
)
_ELEMENT_LINE = "    {label:<44} {base:.2f}→{cur:.2f}  P(reg)={reg:.2f}  [{res}]"


def format_scenario_line(verdict: ScenarioVerdict) -> str:
    """Render the one-line per-scenario total-score verdict."""
    total = verdict.total
    return _SCENARIO_LINE.format(
        sid=verdict.scenario_id,
        mean=total.delta_mean,
        lo=total.ci_low,
        hi=total.ci_high,
        reg=total.p_regression,
        eq=total.p_equivalent,
        imp=total.p_improvement,
    )


def format_portfolio_line(portfolio: PortfolioVerdict) -> str:
    """Render the pooled portfolio-bias verdict line."""
    total = portfolio.total
    return _PORTFOLIO_LINE.format(
        count=portfolio.scenario_count,
        mean=total.delta_mean,
        lo=total.ci_low,
        hi=total.ci_high,
        reg=total.p_regression,
        eq=total.p_equivalent,
        imp=total.p_improvement,
    )


def _format_element_line(element: ElementInferiority) -> str:
    """Render one notable per-element Beta-Binomial row."""
    return _ELEMENT_LINE.format(
        label=element.label[:_LABEL_COL_WIDTH],
        base=element.baseline_rate,
        cur=element.current_rate,
        reg=element.p_regression,
        res=element.resolution,
    )


def notable_elements(verdict: ScenarioVerdict) -> list[ElementInferiority]:
    """Elements whose regression or improvement probability clears the threshold."""
    return [
        element
        for element in verdict.elements
        if max(element.p_regression, element.p_improvement) >= _NOTABLE_THRESHOLD
    ]


def format_scenario_block(verdict: ScenarioVerdict) -> list[str]:
    """Scenario verdict line followed by its notable per-element rows."""
    lines = [format_scenario_line(verdict)]
    lines.extend(_format_element_line(element) for element in notable_elements(verdict))
    return lines
