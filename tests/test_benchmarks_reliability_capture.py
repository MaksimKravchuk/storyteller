"""Tests for benchmarks/harness/_reliability_capture wrappers."""

from __future__ import annotations

import allure

from benchmarks.harness import _reliability_capture as reliability_capture
from cast import _reliability_metrics as reliability_metrics

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Reliability metering"),
]


@allure.story("Benchmarks reset")
@allure.title("reset_for_scenario re-initialises an empty counter map")
def test_reset_for_scenario_initialises_empty_map() -> None:
    reliability_metrics.reliability_counters.set(None)

    reliability_capture.reset_for_scenario()

    assert reliability_metrics.snapshot_counters() == {}


@allure.story("Benchmarks collect")
@allure.title("collect_reliability_counts renders counters into nested per-agent shape")
def test_collect_reliability_counts_nested_shape() -> None:
    reliability_capture.reset_for_scenario()
    reliability_metrics.record_fallback("dramaturge", "consistency_pass")
    reliability_metrics.record_fallback("dramaturge", "scene_dispatch")
    reliability_metrics.record_retry("Director", attempt=1)

    snapshot = reliability_capture.collect_reliability_counts()

    assert snapshot == {
        "Director": {"validation_retry": 1},
        "dramaturge": {"silent_fallback": 2},
    }


@allure.story("Benchmarks collect")
@allure.title("collect_reliability_counts returns {} when no counters recorded")
def test_collect_reliability_counts_empty() -> None:
    reliability_capture.reset_for_scenario()

    assert reliability_capture.collect_reliability_counts() == {}
