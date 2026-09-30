"""Tests for beta LLM pricing and spend reports."""

from __future__ import annotations

from decimal import Decimal

import allure

from config import Config
from costs.model_pricing import ModelPrice, calculate_call_cost_usd, price_for_model
from costs.reports import build_cost_summary

pytestmark = [
    allure.epic("Operations"),
    allure.feature("Cost telemetry"),
    allure.story("Model pricing"),
]


@allure.title("Known model token usage produces an exact Decimal USD cost")
def test_known_model_cost_uses_decimal_prices() -> None:
    result = calculate_call_cost_usd("gpt-6-luna", 1_000_000, 500_000, Config())

    assert result.cost_usd == Decimal("0.350000")
    assert result.unpriced is False
    assert result.missing_usage is False


@allure.title("Checked-in OpenAI prices match the published standard per-1M-token rates")
def test_checked_in_openai_prices_match_published_rates() -> None:
    cfg = Config()

    assert price_for_model("gpt-6-luna", cfg) == ModelPrice(Decimal("0.10"), Decimal("0.50"))
    assert price_for_model("gpt-5.4-mini", cfg) == ModelPrice(Decimal("0.75"), Decimal("4.50"))
    assert price_for_model("gpt-5.4-nano", cfg) == ModelPrice(Decimal("0.20"), Decimal("1.25"))


@allure.title("Unknown model pricing is flagged without crashing")
def test_unknown_model_is_flagged_without_crashing() -> None:
    result = calculate_call_cost_usd("unknown-model", 10, 20, Config())

    assert result.cost_usd == Decimal("0")
    assert result.unpriced is True


@allure.title("Model pricing JSON override replaces a checked-in default")
def test_pricing_json_override_replaces_default() -> None:
    cfg = Config(
        model_pricing_json=('{"gpt-5.4-mini":{"input_per_million_usd":"1.00","output_per_million_usd":"3.00"}}'),
    )

    price = price_for_model("gpt-5.4-mini", cfg)

    assert price is not None
    assert price.input_per_million_usd == Decimal("1.00")
    assert price.output_per_million_usd == Decimal("3.00")


@allure.title("Cost summary redacts prompts and flags missing token usage")
def test_cost_summary_redacts_prompt_material_and_flags_missing_usage() -> None:
    rows = [
        {
            "user_id": "user-1",
            "session_id": "session-1",
            "game_state_id": "game-1",
            "utc_day": "2026-05-24",
            "model": "gpt-5.4-mini",
            "prompt_tokens": 1_000_000,
            "completion_tokens": 500_000,
            "call_count": 2,
            "missing_usage_count": 1,
            "started_at": None,
            "ended_at": None,
            "system_prompt": "do not leak",
            "messages": [{"content": "secret"}],
            "response_content": "hidden",
        },
        {
            "user_id": "user-2",
            "session_id": "session-2",
            "game_state_id": "game-2",
            "utc_day": "2026-05-24",
            "model": "mystery",
            "prompt_tokens": 100,
            "completion_tokens": 100,
            "call_count": 1,
            "missing_usage_count": 0,
            "started_at": None,
            "ended_at": None,
        },
    ]

    summary = build_cost_summary(rows, Config())
    rendered = repr(summary)

    assert summary["total"]["estimated_cost_usd"] == "3.000000"
    assert summary["total"]["missing_usage_count"] == 1
    assert summary["total"]["unpriced_call_count"] == 1
    assert "system_prompt" not in rendered
    assert "messages" not in rendered
    assert "response_content" not in rendered
    assert "secret" not in rendered
