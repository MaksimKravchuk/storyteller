from __future__ import annotations

import asyncio
import types
from typing import Any, Awaitable, Callable

from loguru import logger

from llm._anthropic_schema import harden_anthropic_schema
from llm.base_client import BaseLLMClient, OutputFormat
from llm.message import LLMResponse, Message, Role, Tool, ToolCall

# Bounded backoff for Anthropic 5xx (e.g. transient ``Grammar compilation
# is temporarily unavailable``). Layered on top of the SDK's own retries
# to absorb outages that outlast the SDK's default ~1.5s budget.
_RETRY_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY = 2.0

# Centralised Anthropic payload keys so string literals don't repeat
# through the translation helpers (flake8 WPS226 caps re-use at 3).
_KEY_TYPE = "type"
_TYPE_TOOL = "tool"
_TYPE_AUTO = "auto"
_TYPE_ANY = "any"
_TYPE_NONE = "none"

# Substring marker in Anthropic's 400-response body that means "schema
# exceeds the structured-output beta's grammar-complexity budget". The
# strict path is unrecoverable for this schema, so the client translates
# to ``NotImplementedError`` and ``_send_json`` falls back to the
# prompt-based JSON path.
_SCHEMA_TOO_COMPLEX_MARKER = "Schema is too complex"


_NAMED_CHOICE_MAP: types.MappingProxyType[str, dict[str, Any]] = types.MappingProxyType(
    {
        "auto": {_KEY_TYPE: _TYPE_AUTO},
        "required": {_KEY_TYPE: _TYPE_ANY},
        "none": {_KEY_TYPE: _TYPE_NONE},
    }
)

# Short aliases so tool-translation signatures stay within the
# line-complexity budget.
_WireTools = list[dict[str, Any]]


def _build_tools(tools: tuple[Tool, ...] | None) -> _WireTools | None:
    """Translate tool definitions into Anthropic's ``tools`` payload.

    Anthropic uses ``input_schema`` where OpenAI uses ``parameters``. The
    raw Pydantic schema is passed through verbatim; Anthropic does not
    require the OpenAI-style strict normalization for tool inputs.
    """
    if not tools:
        return None
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters_schema,
        }
        for tool in tools
    ]


def _build_tool_choice(tool_choice: str | None) -> dict[str, Any] | None:
    """Translate the portable ``tool_choice`` knob into Anthropic's shape.

    Mapping: ``"auto"`` → ``{"type": "auto"}``, ``"required"`` →
    ``{"type": "any"}``, tool name → ``{"type": "tool", "name": ...}``.
    """
    if tool_choice is None:
        return None
    mapped = _NAMED_CHOICE_MAP.get(tool_choice)
    if mapped is not None:
        return mapped
    return {_KEY_TYPE: _TYPE_TOOL, "name": tool_choice}


async def _call_with_retry(
    create: Callable[[], Awaitable[Any]],
    max_attempts: int = _RETRY_MAX_ATTEMPTS,
    base_delay: float = _RETRY_BASE_DELAY,
    attempt: int = 0,
) -> Any:
    """Invoke ``create`` with bounded exponential backoff on Anthropic 5xx.

    Retries only on :class:`anthropic.InternalServerError` (e.g. the
    transient ``Grammar compilation is temporarily unavailable`` 503).
    Backoff is ``base_delay * 2**attempt``. Other errors (4xx, validation,
    network) propagate immediately. Implemented via tail recursion so the
    retry loop carries its own attempt counter without an ``await`` inside
    a ``for`` loop body.
    """
    from anthropic import InternalServerError

    try:
        return await create()
    except InternalServerError as exc:
        if attempt + 1 >= max_attempts:
            raise
        delay = base_delay * (2**attempt)
        logger.warning(
            "Anthropic 5xx (attempt {}/{}); retrying in {}s: {}",
            attempt + 1,
            max_attempts,
            delay,
            exc,
        )
        await asyncio.sleep(delay)
    return await _call_with_retry(create, max_attempts, base_delay, attempt + 1)


def _parse_tool_calls(response: Any) -> list[ToolCall]:
    """Extract ``ToolCall`` objects from an Anthropic ``Message`` response.

    Anthropic returns tool invocations as ``tool_use`` blocks inside
    ``response.content``; the ``input`` field is already a dict, so no
    JSON decoding is needed.
    """
    parsed: list[ToolCall] = []
    for block in response.content:
        if getattr(block, _KEY_TYPE, None) != "tool_use":
            continue
        arguments = getattr(block, "input", None) or {}
        parsed.append(
            ToolCall(
                name=block.name,
                arguments=arguments if isinstance(arguments, dict) else {"__raw__": arguments},
                call_id=getattr(block, "id", None),
            ),
        )
    return parsed


class AnthropicClient(BaseLLMClient):
    """Anthropic API provider (Claude models)."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
        **kwargs: Any,
    ):
        super().__init__(model=model, api_key=api_key, **kwargs)
        # Lazy import so anthropic is not required when using another provider
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=self.api_key)
        # Schemas the beta endpoint already rejected as "too complex".
        # Subsequent calls with the same ``schema_name`` skip the strict
        # path entirely so we don't pay the 400-roundtrip every turn.
        self._schemas_skip_strict: set[str] = set()

    async def send_message(
        self,
        messages: list[Message],
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        output_format: OutputFormat | None = None,
    ) -> LLMResponse:
        if output_format is not None and output_format.schema is not None:
            # Raises NotImplementedError before any wire-payload work when the
            # schema has been quarantined (or the model never supported strict
            # outputs), so the prompt-fallback path doesn't pay for kwargs +
            # schema hardening on every turn after the first 400.
            self._guard_strict_supported(output_format.schema_name)
        kwargs = self._build_request_kwargs(
            messages,
            system_prompt,
            temperature,
            max_tokens,
            output_format,
        )
        if output_format is not None and output_format.schema is not None:
            hardened_schema = harden_anthropic_schema(output_format.schema)
            kwargs["output_format"] = {_KEY_TYPE: "json_schema", "schema": hardened_schema}
            response = await self._send_strict(kwargs, output_format.schema_name)
        else:
            response = await _call_with_retry(lambda: self._client.messages.create(**kwargs))

        response_text = ""
        for block in response.content:
            if block.type == "text":
                response_text += block.text

        return LLMResponse(
            body=response_text,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
            },
            model=response.model,
            tool_calls=_parse_tool_calls(response),
        )

    def _guard_strict_supported(self, schema_name: str | None) -> None:
        """Raise ``NotImplementedError`` if strict outputs are off for this schema.

        Two cases: the model never supports structured outputs, or this
        specific schema_name has already been quarantined after a prior
        ``"Schema is too complex."`` 400. Either way the strict path is
        unrecoverable and ``_send_json`` should fall back to the prompt path.
        """
        if not self.supports_structured_output:
            raise NotImplementedError(
                "structured outputs not supported for model={0}".format(self.model),
            )
        if schema_name and schema_name in self._schemas_skip_strict:
            raise NotImplementedError(
                "schema {0!r} previously rejected as too complex; using prompt fallback".format(schema_name),
            )

    async def _send_strict(self, kwargs: dict[str, Any], schema_name: str | None) -> Any:
        """Call the beta endpoint, translating schema-complexity 400s to ``NotImplementedError``.

        Quarantines the offending ``schema_name`` so subsequent calls skip
        the strict path without paying for another rejected roundtrip.
        Other 400s (and all other errors) propagate unchanged so the caller
        sees genuine API failures.
        """
        from anthropic import BadRequestError

        try:
            return await _call_with_retry(lambda: self._client.beta.messages.create(**kwargs))
        except BadRequestError as exc:
            if _SCHEMA_TOO_COMPLEX_MARKER not in str(exc):
                raise
            if schema_name:
                self._schemas_skip_strict.add(schema_name)
            logger.warning(
                "Anthropic rejected schema {!r} as too complex; falling back to prompt-based JSON",
                schema_name,
            )
            raise NotImplementedError(
                "schema {0!r} too complex for Anthropic strict mode".format(schema_name),
            ) from exc

    def _build_request_kwargs(
        self,
        messages: list[Message],
        system_prompt: str,
        temperature: float | None,
        max_tokens: int | None,
        output_format: OutputFormat | None,
    ) -> dict[str, Any]:
        """Build the kwargs dict handed to ``messages.create``.

        Kept separate so :meth:`send_message` stays inside the
        local-variable / argument budget; tool/system translation lives
        here.
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": self._format_messages(messages),
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": self.max_tokens if max_tokens is None else max_tokens,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if output_format is not None and output_format.tools:
            kwargs["tools"] = _build_tools(output_format.tools)
            wire_tool_choice = _build_tool_choice(output_format.tool_choice)
            if wire_tool_choice is not None:
                kwargs["tool_choice"] = wire_tool_choice
        return kwargs

    def _format_messages(self, messages: list[Message]) -> list[dict[str, str]]:
        """Format messages for the Anthropic API.

        Note: Anthropic uses a separate ``system`` parameter rather than a
        system message inside the messages list.
        """
        formatted: list[dict[str, str]] = []
        for msg in messages:
            # Map our Role enum to Anthropic role strings
            role = "user" if msg.role == Role.USER else "assistant"
            formatted.append({"role": role, "content": msg.body})
        return formatted
