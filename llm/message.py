from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(Enum):
    """Message roles for LLM conversations."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    """A single message in a conversation."""

    role: Role
    body: str


@dataclass(frozen=True)
class Tool:
    """A single tool the model may invoke.

    ``parameters_schema`` is a JSON schema (typically produced by
    ``BaseModel.model_json_schema()``). Strict-mode providers may
    normalize the schema further (e.g. OpenAI requires
    ``additionalProperties: false`` on every object). That normalization
    is the provider client's job — callers pass the raw Pydantic schema
    verbatim.
    """

    name: str
    description: str
    parameters_schema: dict[str, Any]


@dataclass
class ToolCall:
    """A single tool invocation returned by the model.

    ``arguments`` is the decoded JSON payload (a dict). Providers that
    return the arguments as a JSON string (OpenAI) decode it before
    building the ``ToolCall``. ``call_id`` is the provider's correlation
    ID when available, so callers that want to feed tool results back
    in a follow-up turn can round-trip it.
    """

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str | None = None


@dataclass(frozen=True)
class OutputFormat:
    """Output-shape controls for a single LLM call.

    Three modes are mutually exclusive at the response-shape level:

    - ``response_format`` — legacy provider-specific dict (e.g.
      ``{"type": "json_object"}`` for OpenAI's JSON mode).
    - ``schema`` / ``schema_name`` — strict structured outputs (Pydantic
      ``model_json_schema()`` compatible). When set, the provider MUST
      honor it or raise ``NotImplementedError``.

    ``tools`` / ``tool_choice`` are orthogonal: a tool-use call normally
    leaves ``response_format`` / ``schema`` unset since the model's output
    arrives on :attr:`llm.message.LLMResponse.tool_calls`. ``tool_choice``
    accepts ``"auto"`` (model picks), ``"required"`` (model must call any
    tool), or a tool name (model must call that specific tool).
    """

    response_format: dict[str, Any] | None = None
    schema: dict[str, Any] | None = None
    schema_name: str | None = None
    tools: tuple[Tool, ...] | None = None
    tool_choice: str | None = None


@dataclass
class LLMResponse:
    """Response from an LLM provider.

    ``body`` is the plain-text response (may be empty when the model
    only returned tool calls). ``tool_calls`` is the decoded list of
    tool invocations the model requested this turn; empty when no tools
    were exposed or the model chose not to call one.
    """

    body: str
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
