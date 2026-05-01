"""Schema-hardening helpers for the Anthropic structured-output beta.

Pydantic's ``model_json_schema()`` emits a few shapes the Anthropic beta
endpoint rejects: ``"type": "object"`` nodes without
``additionalProperties: false``, ``minimum``/``maximum`` constraints on
``"type": "integer"`` nodes, and cosmetic metadata (``title``,
``description``, ``default``, ``examples``) that pushes the schema past
the endpoint's ``"Schema is too complex."`` budget.

:func:`harden_anthropic_schema` returns a fresh, normalised copy so
caller-owned schema dicts are never mutated.
"""

from __future__ import annotations

from typing import Any

_KEY_TYPE = "type"

# Numeric range constraints Anthropic's structured-output beta rejects on
# ``"type": "integer"`` nodes (``"For 'integer' type, properties maximum,
# minimum are not supported"``).
_INTEGER_RANGE_KEYS = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")

# Cosmetic metadata that inflates Anthropic's schema-complexity score
# without affecting validation. ``default`` is metadata-only in JSON
# schema; pydantic still applies python-level defaults when deserialising
# the LLM response.
_NOISE_KEYS = ("title", "description", "default", "examples")

# JSON-schema keys whose value is a *mapping* of user-defined names (not
# reserved schema keywords). Their immediate children must be walked
# without applying ``_NOISE_KEYS`` to the property names — otherwise a
# field literally named ``description`` (e.g. ``NPCGoalDraft.description``)
# would be silently dropped from ``properties``.
_PROPERTY_MAP_KEYS = ("properties", "$defs", "definitions", "patternProperties")


def harden_anthropic_schema(node: Any) -> Any:
    """Return a normalised copy of ``node`` ready for the beta endpoint."""
    if isinstance(node, dict):
        return _harden_dict(node)
    if isinstance(node, list):
        return [harden_anthropic_schema(child) for child in node]
    return node


def _harden_dict(node: dict[str, Any]) -> dict[str, Any]:
    """Apply node-level constraints after recursing into the dict's children."""
    walked: dict[str, Any] = {}
    for key, raw_value in node.items():
        if key in _NOISE_KEYS:
            continue
        walked[key] = _walk_value(key, raw_value)
    return _stamp_constraints(walked)


def _walk_value(key: str, raw_value: Any) -> Any:
    """Pick the right walker for ``raw_value`` based on its parent ``key``."""
    if key in _PROPERTY_MAP_KEYS and isinstance(raw_value, dict):
        return {prop_name: harden_anthropic_schema(prop_schema) for prop_name, prop_schema in raw_value.items()}
    return harden_anthropic_schema(raw_value)


def _stamp_constraints(node: dict[str, Any]) -> dict[str, Any]:
    """Stamp ``additionalProperties: false`` and strip integer ranges."""
    node_type = node.get(_KEY_TYPE)
    if node_type == "object" and "additionalProperties" not in node:
        node["additionalProperties"] = False
    if node_type == "integer":
        for unsupported in _INTEGER_RANGE_KEYS:
            node.pop(unsupported, None)
    return node
