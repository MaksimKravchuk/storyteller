"""Scenario binding for the scene-builder re-entry-consistency benchmark."""

from __future__ import annotations

from benchmarks.harness.types._scenarios import Scenario
from benchmarks.scenarios.scene_builder_re_entry_consistency.elements import ELEMENTS
from benchmarks.scenarios.scene_builder_re_entry_consistency.script import SCRIPT
from benchmarks.scenarios.scene_builder_re_entry_consistency.state import build_state

SCENARIO: Scenario = Scenario(
    id="scene_builder_re_entry_consistency",
    label="SceneBuilder preserves Forum landmarks when the player leaves and returns",
    build_state=build_state,
    script=SCRIPT,
    elements=ELEMENTS,
)
