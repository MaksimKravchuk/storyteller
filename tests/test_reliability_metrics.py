"""Tests for cast/_reliability_metrics contextvar counters."""

from __future__ import annotations

import allure

from cast import _reliability_metrics as reliability_metrics

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Reliability metering"),
]


@allure.story("Counter reset")
@allure.title("reset_counters initialises an empty counter map")
def test_reset_initialises_empty_map():
    reliability_metrics.reliability_counters.set(None)

    reliability_metrics.reset_counters()

    assert reliability_metrics.snapshot_counters() == {}


@allure.story("Counter reset")
@allure.title("reset_counters clears prior counts")
def test_reset_clears_prior_counts():
    reliability_metrics.reset_counters()
    reliability_metrics.record_fallback("narrator", "visible_entities")

    reliability_metrics.reset_counters()

    assert reliability_metrics.snapshot_counters() == {}


@allure.story("Record fallback")
@allure.title("record_fallback is a no-op when counters were never reset")
def test_record_fallback_noop_without_reset():
    reliability_metrics.reliability_counters.set(None)

    reliability_metrics.record_fallback("dramaturge", "consistency_pass")

    assert reliability_metrics.snapshot_counters() == {}


@allure.story("Record fallback")
@allure.title("record_fallback increments the matching agent+event_type cell")
def test_record_fallback_increments_cell():
    reliability_metrics.reset_counters()

    reliability_metrics.record_fallback("dramaturge", "consistency_pass")
    reliability_metrics.record_fallback("dramaturge", "scene_dispatch")
    reliability_metrics.record_fallback("dramaturge", "any_reason_again")

    snapshot = reliability_metrics.snapshot_counters()
    assert snapshot == {("dramaturge", "silent_fallback"): 3}


@allure.story("Record retry")
@allure.title("record_retry increments the validation_retry cell once per call")
def test_record_retry_increments_per_attempt():
    reliability_metrics.reset_counters()

    reliability_metrics.record_retry("Director", attempt=1)
    reliability_metrics.record_retry("Director", attempt=2)

    snapshot = reliability_metrics.snapshot_counters()
    assert snapshot == {("Director", "validation_retry"): 2}


@allure.story("Snapshot")
@allure.title("snapshot_counters returns a copy independent of further mutations")
def test_snapshot_is_independent_copy():
    reliability_metrics.reset_counters()
    reliability_metrics.record_fallback("narrator", "visible_entities")

    snapshot = reliability_metrics.snapshot_counters()
    reliability_metrics.record_fallback("narrator", "another")

    assert snapshot == {("narrator", "silent_fallback"): 1}
    assert reliability_metrics.snapshot_counters() == {("narrator", "silent_fallback"): 2}


@allure.story("Snapshot")
@allure.title("snapshot_counters returns {} when counters were never initialised")
def test_snapshot_returns_empty_when_uninitialised():
    reliability_metrics.reliability_counters.set(None)

    assert reliability_metrics.snapshot_counters() == {}


@allure.story("Multi-agent")
@allure.title("counters segregate by agent name")
def test_counters_segregate_by_agent():
    reliability_metrics.reset_counters()

    reliability_metrics.record_fallback("dramaturge", "consistency_pass")
    reliability_metrics.record_fallback("narrator", "visible_entities")
    reliability_metrics.record_retry("Director", attempt=1)

    snapshot = reliability_metrics.snapshot_counters()
    assert snapshot == {
        ("dramaturge", "silent_fallback"): 1,
        ("narrator", "silent_fallback"): 1,
        ("Director", "validation_retry"): 1,
    }
