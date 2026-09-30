"""Deterministic LLM token pricing helpers for beta spend reports."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from config import Config

_ONE_MILLION = Decimal("1000000")
# Providers answer with a dated snapshot id (``gpt-6-luna-2026-05-18``) that
# call logs persist verbatim; prices are keyed by the base model id.
_SNAPSHOT_SUFFIX = re.compile(r"-\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class ModelPrice:
    """USD price per one million input and output tokens."""

    input_per_million_usd: Decimal
    output_per_million_usd: Decimal


@dataclass(frozen=True)
class CallCost:
    """Cost calculation result plus report flags."""

    cost_usd: Decimal
    unpriced: bool
    missing_usage: bool


DEFAULT_MODEL_PRICES = MappingProxyType(
    {
        "gpt-6-luna": ModelPrice(Decimal("0.100"), Decimal("0.500")),
        "gpt-5.4-mini": ModelPrice(Decimal("0.750"), Decimal("4.500")),
        "gpt-5.4-nano": ModelPrice(Decimal("0.200"), Decimal("1.250")),
    },
)


def _decimal_from_config(raw_value: Any) -> Decimal:
    """Convert an env/JSON value to Decimal without binary-float artifacts."""
    return Decimal(str(raw_value))


def _price_from_mapping(raw: dict[str, Any]) -> ModelPrice:
    """Build a ModelPrice from accepted JSON field spellings."""
    input_price = raw.get("input_per_million_usd", raw.get("prompt_per_million_usd"))
    output_price = raw.get("output_per_million_usd", raw.get("completion_per_million_usd"))
    if input_price is None or output_price is None:
        raise ValueError("model pricing entries need input/output per-million USD fields")
    return ModelPrice(
        input_per_million_usd=_decimal_from_config(input_price),
        output_per_million_usd=_decimal_from_config(output_price),
    )


def configured_prices(cfg: Config) -> dict[str, ModelPrice]:
    """Return default model prices with optional JSON overrides applied."""
    prices = dict(DEFAULT_MODEL_PRICES)
    if not cfg.model_pricing_json:
        return prices
    raw_prices = json.loads(cfg.model_pricing_json)
    if not isinstance(raw_prices, dict):
        raise ValueError("model pricing JSON must be an object keyed by model id")
    for model, raw_entry in raw_prices.items():
        if not isinstance(raw_entry, dict):
            raise ValueError("model pricing JSON values must be objects")
        prices[str(model)] = _price_from_mapping(raw_entry)
    return prices


def price_for_model(model: str | None, cfg: Config) -> ModelPrice | None:
    """Return pricing for a model, or None when it is unknown."""
    if model is None:
        return None
    prices = configured_prices(cfg)
    return prices.get(model) or prices.get(_SNAPSHOT_SUFFIX.sub("", model))


def calculate_call_cost_usd(
    model: str | None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    cfg: Config,
) -> CallCost:
    """Calculate one call's estimated cost using Decimal math.

    Unknown models and missing token usage never raise; callers can surface the
    returned flags in reports while treating the cost as zero.
    """
    price = price_for_model(model, cfg)
    missing_usage = prompt_tokens is None or completion_tokens is None
    if price is None:
        return CallCost(Decimal("0"), unpriced=True, missing_usage=missing_usage)
    if prompt_tokens is None or completion_tokens is None:
        return CallCost(Decimal("0"), unpriced=False, missing_usage=True)
    prompt_cost = Decimal(int(prompt_tokens)) * price.input_per_million_usd / _ONE_MILLION
    completion_cost = Decimal(int(completion_tokens)) * price.output_per_million_usd / _ONE_MILLION
    return CallCost((prompt_cost + completion_cost).quantize(Decimal("0.000001")), False, False)
