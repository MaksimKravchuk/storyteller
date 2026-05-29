"""Tests for llm._anthropic_schema.harden_anthropic_schema — schema normalisation rules.

The hardener is exercised end-to-end via AnthropicClient, but the rules it
enforces are easier to lock down at the function level: each rule is one
shape the Anthropic beta endpoint refuses.
"""

from __future__ import annotations

from typing import Annotated

import allure
import pytest
from pydantic import BaseModel, Field

from llm._anthropic_schema import harden_anthropic_schema


class _EnvelopeWithCappedList(BaseModel):
    """Pydantic stand-in for the ActorEnvelope shape that originally tripped the bug.

    ``Field(max_length=...)`` on a ``list[...]`` is the exact construction
    that surfaced ``"For 'array' type, property 'maxItems' is not supported"``
    from Anthropic's beta endpoint.
    """

    names: Annotated[list[str], Field(max_length=8)] = []


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Anthropic client")
class TestHardenAnthropicSchema:
    @allure.story("Schema hardening")
    @allure.title("harden_anthropic_schema leaves maxItems intact on non-array nodes")
    def test_preserves_max_items_on_non_array_nodes(self) -> None:
        # Defensive: ``maxItems`` is only forbidden on ``"type": "array"`` —
        # if it ever showed up under a different type the hardener should
        # leave it alone rather than silently rewrite an unrelated schema.
        schema = {"type": "object", "maxItems": 5}

        hardened = harden_anthropic_schema(schema)

        assert hardened["maxItems"] == 5

    @allure.story("Schema hardening")
    @allure.title("Pydantic Field(max_length=...) on a list is normalised so Anthropic accepts the schema")
    def test_pydantic_list_field_with_max_length_is_hardened(self) -> None:
        # Regression: ``ActorEnvelope.revealed_names`` declared
        # ``Field(max_length=8)`` on a list, which pydantic emits as
        # ``"maxItems": 8`` — Anthropic's beta endpoint then 400s with
        # ``"For 'array' type, property 'maxItems' is not supported"``.
        raw = _EnvelopeWithCappedList.model_json_schema()
        assert raw["properties"]["names"]["maxItems"] == 8

        hardened = harden_anthropic_schema(raw)
        assert "maxItems" not in hardened["properties"]["names"]

    @allure.story("Schema hardening")
    @allure.title("harden_anthropic_schema still strips minimum and maximum from integer nodes")
    def test_still_strips_integer_range_keys(self) -> None:
        schema = {"type": "integer", "minimum": 0, "maximum": 10}

        hardened = harden_anthropic_schema(schema)

        assert "minimum" not in hardened
        assert "maximum" not in hardened

    @allure.story("Schema hardening")
    @allure.title("harden_anthropic_schema returns a normalised copy without mutating the caller's dict")
    def test_does_not_mutate_caller_schema(self) -> None:
        schema = {"type": "array", "items": {"type": "string"}, "maxItems": 4}

        harden_anthropic_schema(schema)

        assert schema["maxItems"] == 4


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Anthropic client")
@allure.story("Schema hardening")
@allure.title("Each Anthropic-forbidden array constraint is stripped individually: {array_key}")
@pytest.mark.parametrize("array_key", ["minItems", "maxItems", "uniqueItems"])
def test_each_array_constraint_is_individually_stripped(array_key: str) -> None:
    schema = {"type": "array", "items": {"type": "string"}, array_key: 3}

    hardened = harden_anthropic_schema(schema)

    assert array_key not in hardened
