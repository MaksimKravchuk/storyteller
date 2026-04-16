"""Scenario binding for the KER-23 escalation regression benchmark."""

from __future__ import annotations

from benchmarks.harness.types._scenarios import Scenario
from benchmarks.scenarios.escalation_guard_assault.elements import ELEMENTS
from benchmarks.scenarios.escalation_guard_assault.script import SCRIPT
from benchmarks.scenarios.escalation_guard_assault.state import build_state

SCENARIO: Scenario = Scenario(
    id="escalation_guard_assault",
    label="Escalation — repeat assault on a lone sentry (KER-23 regression)",
    build_state=build_state,
    script=SCRIPT,
    elements=ELEMENTS,
)
