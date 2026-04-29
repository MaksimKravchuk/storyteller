from __future__ import annotations

import copy
import json
from typing import TYPE_CHECKING, Any

from loguru import logger

from llm.base_client import BaseLLMClient, OutputFormat
from llm.message import LLMResponse, Message, Tool, ToolCall

if TYPE_CHECKING:
    from openai import APIStatusError


_ALLOWED_CONTROL = frozenset("\t\n\r")
_SYSTEM_PROMPT_LOG_CHARS = 200

# Centralised OpenAI payload keys so the string doesn't repeat through the
# translation helpers (flake8 WPS226 caps literal re-use at 3).
_KEY_TYPE = "type"
_TYPE_JSON_SCHEMA = "json_schema"
_TYPE_FUNCTION = "function"

# Short aliases to keep tool translation signatures readable (flake8 WPS221).
_WireTools = list[dict[str, Any]]
_WireToolChoice = Any


def _is_printable(ch: str) -> bool:
    """Return True if the character is safe for JSON strings."""
    return (ch >= "\x20" and ch != "\x7f") or ch in _ALLOWED_CONTROL


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


def _build_response_format(output_format: OutputFormat | None) -> dict[str, Any] | None:
    """Translate an ``OutputFormat`` into the OpenAI ``response_format`` payload.

    Returns ``None`` when the caller did not request any specific format.
    Strict mode (``output_format.schema is not None``) wins over the legacy dict.
    """
    if output_format is None:
        return None
    if output_format.schema is not None:
        return _StrictSchemaNormalizer.wrap(
            output_format.schema,
            output_format.schema_name or "Response",
        )
    return output_format.response_format


class _ToolWire:
    """Translate provider-agnostic tool types into OpenAI's wire payload.

    Grouped as classmethods so the module stays within the flake8
    module-member budget. The class is a namespace only; it's never
    instantiated.
    """

    # Tool parameter schemas are static (built once at module load from
    # Pydantic models) and live for the process lifetime, so keying the
    # cache on ``id(schema)`` is safe: the schema objects are never
    # garbage-collected, and IDs therefore never get reused out from
    # under the cache. Callers that build tools dynamically (outside
    # ACTION_TOOLS) would need a different strategy.
    _normalized_cache: dict[int, dict[str, Any]] = {}

    @classmethod
    def normalize_parameters(cls, schema: dict[str, Any]) -> dict[str, Any]:
        """Apply OpenAI strict-function constraints to a tool's parameters schema."""
        cached = cls._normalized_cache.get(id(schema))
        if cached is not None:
            return cached
        normalized = copy.deepcopy(schema)
        _StrictSchemaNormalizer._walk(normalized)
        cls._normalized_cache[id(schema)] = normalized
        return normalized

    @classmethod
    def build_tools(cls, tools: tuple[Tool, ...] | None) -> _WireTools | None:
        """Translate tool definitions into the OpenAI ``tools`` payload.

        Returns ``None`` when no tools are exposed this call, so the key
        is omitted from the request entirely.
        """
        if not tools:
            return None
        return [cls._tool_wire_entry(tool) for tool in tools]

    @classmethod
    def build_tool_choice(cls, tool_choice: str | None) -> _WireToolChoice:
        """Translate the portable ``tool_choice`` knob into OpenAI's shape.

        Accepts ``"auto"``, ``"required"``, or a tool name (forces that
        specific function). Returns ``None`` when the caller did not pin
        a choice; OpenAI defaults to ``"auto"`` in that case.
        """
        if tool_choice is None:
            return None
        if tool_choice in {"auto", "required", "none"}:
            return tool_choice
        return {_KEY_TYPE: _TYPE_FUNCTION, _TYPE_FUNCTION: {"name": tool_choice}}

    @classmethod
    def parse_calls(cls, choice: Any) -> list[ToolCall]:
        """Extract ``ToolCall`` objects from an OpenAI ``ChatCompletion`` choice.

        OpenAI returns ``arguments`` as a JSON string; we decode it here
        so callers always see a ``dict``. Malformed JSON is wrapped into
        ``{"__raw__": <string>}`` rather than crashing, so the raw payload
        remains available for assertions and log inspection.
        """
        raw_calls = getattr(choice.message, "tool_calls", None) or []
        parsed = [cls._build_tool_call(raw) for raw in raw_calls]
        return [call for call in parsed if call is not None]

    @classmethod
    def _tool_wire_entry(cls, tool: Tool) -> dict[str, Any]:
        """Build one ``{"type": "function", ...}`` entry for OpenAI."""
        return {
            _KEY_TYPE: _TYPE_FUNCTION,
            _TYPE_FUNCTION: {
                "name": tool.name,
                "description": tool.description,
                "parameters": cls.normalize_parameters(tool.parameters_schema),
                "strict": True,
            },
        }

    @classmethod
    def _build_tool_call(cls, raw: Any) -> ToolCall | None:
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


def _extract_error_body(exc: Any) -> Any:
    """Return the structured body from an OpenAI ``APIStatusError``, or str(exc)."""
    return getattr(exc, "body", None) or str(exc)


def _sanitize(text: str) -> str:
    """Strip characters that break JSON serialization or OpenAI's HTTP parser.

    Handles lone surrogates, null bytes, and other control characters
    (below 0x20 or 0x7F) that are illegal in JSON strings. Tab, newline,
    and carriage-return are preserved.
    """
    # Replace lone surrogates first
    cleaned = text.encode("utf-8", "surrogatepass").decode("utf-8", "replace")
    # Strip null bytes and other control characters illegal in JSON strings
    # Keep \t (0x09), \n (0x0A), \r (0x0D); remove everything else below 0x20 and 0x7F
    return "".join(ch for ch in cleaned if _is_printable(ch))


class OpenAIClient(BaseLLMClient):
    """OpenAI API provider (GPT-5.4 family, GPT-4o, etc.)."""

    def __init__(
        self,
        model: str = "gpt-5.4-mini",
        api_key: str | None = None,
        **kwargs: Any,
    ):
        super().__init__(model=model, api_key=api_key, **kwargs)
        # Lazy import so openai is not required when using another provider
        from openai import APIStatusError, AsyncOpenAI

        self._client = AsyncOpenAI(api_key=self.api_key)
        # Stored as an instance attribute so ``except self._api_status_error``
        # works without a top-level import of ``openai``.
        self._api_status_error: type[APIStatusError] = APIStatusError

    async def send_message(
        self,
        messages: list[Message],
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        output_format: OutputFormat | None = None,
    ) -> LLMResponse:
        kwargs = self._build_request_kwargs(
            messages,
            system_prompt,
            temperature,
            max_tokens,
            output_format,
        )
        try:
            response = await self._client.chat.completions.create(**kwargs)
        except self._api_status_error as exc:
            self._log_api_error(exc, kwargs, system_prompt)
            raise
        choice = response.choices[0]

        return LLMResponse(
            body=choice.message.content or "",
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            model=response.model,
            tool_calls=_ToolWire.parse_calls(choice),
        )

    def _build_request_kwargs(
        self,
        messages: list[Message],
        system_prompt: str,
        temperature: float | None,
        max_tokens: int | None,
        output_format: OutputFormat | None,
    ) -> dict[str, Any]:
        """Build the kwargs dict handed to ``chat.completions.create``.

        Kept separate so :meth:`send_message` stays within the flake8
        local-variable budget; the translation logic lives here.
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": self._format_messages(messages, system_prompt),
            "temperature": self.temperature if temperature is None else temperature,
            "max_completion_tokens": self.max_tokens if max_tokens is None else max_tokens,
        }
        wire_response_format = _build_response_format(output_format)
        if wire_response_format is not None:
            kwargs["response_format"] = wire_response_format
        if output_format is not None and output_format.tools:
            kwargs["tools"] = _ToolWire.build_tools(output_format.tools)
            wire_tool_choice = _ToolWire.build_tool_choice(output_format.tool_choice)
            if wire_tool_choice is not None:
                kwargs["tool_choice"] = wire_tool_choice
        return kwargs

    def _format_messages(
        self,
        messages: list[Message],
        system_prompt: str = "",
    ) -> list[dict[str, str]]:
        formatted: list[dict[str, str]] = []
        if system_prompt:
            formatted.append({"role": "system", "content": _sanitize(system_prompt)})
        for msg in messages:
            sanitized_body = _sanitize(msg.body)
            formatted.append({"role": msg.role.value, "content": sanitized_body})
        return formatted

    def _log_api_error(
        self,
        exc: "APIStatusError",
        kwargs: dict[str, Any],
        system_prompt: str,
    ) -> None:
        """Log the OpenAI error body so the caller can see what the API rejected.

        The whole emit is guarded so that a logging failure can never mask
        the original API error.
        """
        try:
            self._emit_api_error_log(exc, kwargs, system_prompt)
        except Exception:  # noqa: BLE001 - logging must never mask the real error
            logger.exception("Failed to serialize OpenAI API error for logging")

    def _emit_api_error_log(
        self,
        exc: "APIStatusError",
        kwargs: dict[str, Any],
        system_prompt: str,
    ) -> None:
        """Emit the structured error log entry for an OpenAI API failure."""
        logger.error(
            "OpenAI API error | model={} status={} "
            "has_response_format={} num_messages={} temperature={} "
            "max_completion_tokens={} system_prompt[:{}]={!r} body={!r}",
            self.model,
            getattr(exc, "status_code", None),
            "response_format" in kwargs,
            len(kwargs.get("messages", [])),
            kwargs.get("temperature"),
            kwargs.get("max_completion_tokens"),
            _SYSTEM_PROMPT_LOG_CHARS,
            system_prompt[:_SYSTEM_PROMPT_LOG_CHARS],
            _extract_error_body(exc),
        )
