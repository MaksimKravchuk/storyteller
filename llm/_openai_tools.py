"""OpenAI wire-format translation helpers for tools and strict schemas."""

from __future__ import annotations

import copy
import json
from typing import Any

from llm.message import Tool, ToolCall

# Centralised OpenAI payload keys so the string doesn't repeat through the
# translation helpers (flake8 WPS226 caps literal re-use at 3).
_KEY_TYPE = "type"
_TYPE_JSON_SCHEMA = "json_schema"
_TYPE_FUNCTION = "function"

# Type alias for the OpenAI ``tools`` wire payload kept to one name so
# signatures stay within the WPS221 Jones-complexity limit.
_WireToolsList = list[dict[str, Any]]


class _StrictSchemaNormalizer:
    """Convert a Pydantic JSON schema into OpenAI's strict ``response_format`` envelope.

    OpenAI's strict validator requires ``additionalProperties: false`` on
    every object, lists every defined property as ``required`` (even ones
    Pydantic considered optional), and forbids ``default`` keys.
    """

    _composites: tuple[str, ...] = ("anyOf", "oneOf", "allOf")

    @classmethod
    def wrap(cls, schema: dict[str, Any], name: str) -> dict[str, Any]:
        """Return the full ``{"type": "json_schema", ...}`` payload.

        The input ``schema`` is never mutated — a deep copy is normalized
        in place before being returned inside the envelope.

        Note: Pydantic fields with defaults (e.g. ``scope: Literal["local",
        "remote"] = "remote"``) emit a ``default`` key that OpenAI's strict
        validator forbids. We strip it, so the LLM is now *required* to
        produce the field explicitly — the Pydantic default no longer fills
        in on LLM omission because strict mode does not allow omissions.
        Behavior-compatible for enum/literal fields (the LLM just picks a
        valid value), but worth knowing when adding new optional fields.
        """
        normalized = copy.deepcopy(schema)
        cls._walk(normalized)
        return {
            _KEY_TYPE: _TYPE_JSON_SCHEMA,
            _TYPE_JSON_SCHEMA: {
                "name": name,
                "schema": normalized,
                "strict": True,
            },
        }

    @classmethod
    def _walk(cls, node: Any) -> None:
        """Recursively normalize a JSON-schema node in place."""
        if not isinstance(node, dict):
            return
        node.pop("default", None)
        if node.get("type") == "object" or "properties" in node:
            cls._normalize_object(node)
        cls._walk_children(node)
        cls._walk_composites(node)

    @classmethod
    def _normalize_object(cls, node: dict[str, Any]) -> None:
        """Apply object-level strict-mode constraints (``additionalProperties``, ``required``)."""
        properties = node.get("properties")
        if not isinstance(properties, dict):
            return
        node["additionalProperties"] = False
        node["required"] = list(properties.keys())
        for prop_schema in properties.values():
            if isinstance(prop_schema, dict):
                cls._walk(prop_schema)

    @classmethod
    def _walk_children(cls, node: dict[str, Any]) -> None:
        """Descend into array items and ``$defs`` definitions if present."""
        array_items = node.get("items")
        if isinstance(array_items, dict):
            cls._walk(array_items)
        defs = node.get("$defs")
        if isinstance(defs, dict):
            for def_schema in defs.values():
                cls._walk(def_schema)

    @classmethod
    def _walk_composites(cls, node: dict[str, Any]) -> None:
        """Recurse into ``anyOf`` / ``oneOf`` / ``allOf`` branches if present."""
        for composite_key in cls._composites:
            composite = node.get(composite_key)
            if isinstance(composite, list):
                for branch in composite:
                    cls._walk(branch)


def _normalize_tool_parameters(schema: dict[str, Any]) -> dict[str, Any]:
    """Apply OpenAI strict-function constraints to a tool's parameters schema."""
    normalized = copy.deepcopy(schema)
    _StrictSchemaNormalizer._walk(normalized)
    return normalized


def _build_wire_tools(tools: tuple[Tool, ...] | None) -> _WireToolsList | None:
    """Translate tool definitions into the OpenAI ``tools`` payload.

    Returns ``None`` when no tools are exposed this call, so the key
    is omitted from the request entirely.
    """
    if not tools:
        return None
    return [_wire_tool_entry(tool) for tool in tools]


def _build_wire_tool_choice(tool_choice: str | None) -> Any:
    """Translate the portable ``tool_choice`` knob into OpenAI's shape.

    Accepts ``"auto"``, ``"required"``, or a tool name (forces that
    specific function). Returns ``None`` when the caller did not pin
    a choice; OpenAI defaults to ``"auto"`` in that case.
    """
    if tool_choice is None:
        return None
    if tool_choice in {"auto", "required", "none"}:
        return tool_choice
    name_entry: dict[str, Any] = {"name": tool_choice}
    return {_KEY_TYPE: _TYPE_FUNCTION, _TYPE_FUNCTION: name_entry}


def _parse_response_tool_calls(choice: Any) -> list[ToolCall]:
    """Extract ``ToolCall`` objects from an OpenAI ``ChatCompletion`` choice.

    OpenAI returns ``arguments`` as a JSON string; we decode it here
    so callers always see a ``dict``. Malformed JSON is wrapped into
    ``{"__raw__": <string>}`` rather than crashing, so the raw payload
    remains available for assertions and log inspection.
    """
    raw_calls = getattr(choice.message, "tool_calls", None) or []
    parsed = [_build_tool_call_obj(raw) for raw in raw_calls]
    return [call for call in parsed if call is not None]


def _wire_tool_entry(tool: Tool) -> dict[str, Any]:
    """Build one ``{"type": "function", ...}`` entry for OpenAI."""
    return {
        _KEY_TYPE: _TYPE_FUNCTION,
        _TYPE_FUNCTION: {
            "name": tool.name,
            "description": tool.description,
            "parameters": _normalize_tool_parameters(tool.parameters_schema),
            "strict": True,
        },
    }


def _build_tool_call_obj(raw: Any) -> ToolCall | None:
    """Build one :class:`ToolCall` from an OpenAI SDK tool-call object."""
    fn = getattr(raw, _TYPE_FUNCTION, None)
    if fn is None:
        return None
    arguments_str = fn.arguments or "{}"
    try:
        arguments = json.loads(arguments_str)
    except json.JSONDecodeError:
        arguments = {"__raw__": arguments_str}
    return ToolCall(
        name=fn.name,
        arguments=arguments if isinstance(arguments, dict) else {"__raw__": arguments_str},
        call_id=getattr(raw, "id", None),
    )
