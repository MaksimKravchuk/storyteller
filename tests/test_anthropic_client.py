"""Tests for llm.anthropic_client.AnthropicClient — SDK wiring, blocks, streaming, roles."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import httpx
import pytest
from anthropic import BadRequestError, InternalServerError

from llm import message as msg
from llm.anthropic_client import AnthropicClient, _call_with_retry
from llm.base_client import OutputFormat
from llm.message import Tool

_ANTHROPIC_CTOR = "anthropic.AsyncAnthropic"
_MODEL = "claude-sonnet-4-20250514"


def _make_anthropic_5xx(message: str = "Grammar compilation is temporarily unavailable.") -> InternalServerError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(503, request=request)
    return InternalServerError(message, response=response, body=None)


def _make_anthropic_400() -> BadRequestError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(400, request=request)
    return BadRequestError("bad", response=response, body=None)


def _text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _tool_block(name: str = "noop", input: dict | None = None, block_id: str = "toolu_x") -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", name=name, input=input or {}, id=block_id)


def _make_response(
    blocks: list[SimpleNamespace] | None = None,
    input_tokens: int = 7,
    output_tokens: int = 2,
) -> SimpleNamespace:
    content_blocks = [_text_block("hello")] if blocks is None else blocks
    return SimpleNamespace(
        content=content_blocks,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        model=_MODEL,
    )


def _install_sdk_mock(response: SimpleNamespace | None = None) -> tuple[MagicMock, AsyncMock]:
    sdk_class = MagicMock()
    sdk_instance = MagicMock()
    payload = _make_response() if response is None else response
    create_mock = AsyncMock(return_value=payload)
    sdk_instance.messages.create = create_mock
    sdk_class.return_value = sdk_instance
    return sdk_class, create_mock


def _install_beta_sdk_mock(
    response: SimpleNamespace | None = None,
    side_effect: BaseException | None = None,
) -> tuple[MagicMock, AsyncMock]:
    """Patch AsyncAnthropic and wire its ``beta.messages.create`` async mock."""
    sdk_class = MagicMock()
    sdk_instance = MagicMock()
    if side_effect is None:
        payload = _make_response() if response is None else response
        beta_create = AsyncMock(return_value=payload)
    else:
        beta_create = AsyncMock(side_effect=side_effect)
    sdk_instance.beta.messages.create = beta_create
    sdk_class.return_value = sdk_instance
    return sdk_class, beta_create


def _user_msg(body: str = "hi") -> msg.Message:
    return msg.Message(role=msg.Role.USER, body=body)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Anthropic client")
class TestAnthropicClient:
    @allure.story("Constructor")
    @allure.title("AnthropicClient instantiates AsyncAnthropic with the supplied api_key on construction")
    def test_constructor_wires_sdk(self) -> None:
        sdk_class, _ = _install_sdk_mock()
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="ak-xyz")
        sdk_class.assert_called_once_with(api_key="ak-xyz", timeout=120)
        assert client.model == _MODEL

    @allure.story("send_message")
    @allure.title("AnthropicClient.send_message concatenates text blocks and ignores non-text content blocks")
    @pytest.mark.asyncio
    async def test_send_message_text_block_concatenation(self) -> None:
        response = _make_response(
            blocks=[_text_block("Hello, "), _tool_block(), _text_block("world!")],
        )
        sdk_class, create_mock = _install_sdk_mock(response)
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            result = await client.send_message(
                messages=[_user_msg()],
                system_prompt="you are helpful",
            )
        kwargs = create_mock.call_args.kwargs
        assert kwargs["model"] == _MODEL
        assert kwargs["system"] == "you are helpful"
        assert kwargs["temperature"] == pytest.approx(0.7)
        assert kwargs["max_tokens"] == 2048
        assert result.body == "Hello, world!"
        assert result.usage == {"prompt_tokens": 7, "completion_tokens": 2}
        assert result.model == _MODEL

    @allure.story("Tool calls")
    @allure.title("AnthropicClient.send_message serialises tools into the messages.create payload")
    @pytest.mark.asyncio
    async def test_send_message_serialises_tools(self) -> None:
        sdk_class, create_mock = _install_sdk_mock()
        tool = Tool(
            name="move",
            description="Player moves.",
            parameters_schema={
                "type": "object",
                "properties": {"direction": {"type": "string"}},
            },
        )
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            await client.send_message(
                messages=[_user_msg()],
                output_format=OutputFormat(tools=(tool,), tool_choice="required"),
            )
        kwargs = create_mock.call_args.kwargs
        assert kwargs["tool_choice"] == {"type": "any"}
        wire_tools = kwargs["tools"]
        assert len(wire_tools) == 1
        wire_tool = wire_tools[0]
        assert wire_tool["name"] == "move"
        direction_schema = wire_tool["input_schema"]["properties"]["direction"]
        assert direction_schema["type"] == "string"

    @allure.story("Tool calls")
    @allure.title("AnthropicClient.send_message maps a tool name in tool_choice to the Anthropic dict shape")
    @pytest.mark.asyncio
    async def test_tool_choice_by_name(self) -> None:
        sdk_class, create_mock = _install_sdk_mock()
        tool = Tool(name="talk", description="Player talks.", parameters_schema={"type": "object"})
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            await client.send_message(
                messages=[_user_msg()],
                output_format=OutputFormat(tools=(tool,), tool_choice="talk"),
            )
        assert create_mock.call_args.kwargs["tool_choice"] == {"type": "tool", "name": "talk"}

    @allure.story("Tool calls")
    @allure.title("AnthropicClient.send_message parses tool_use blocks into ToolCall objects")
    @pytest.mark.asyncio
    async def test_send_message_parses_tool_calls(self) -> None:
        response = _make_response(
            blocks=[
                _text_block("prelude"),
                _tool_block(name="move", input={"direction": "north"}, block_id="toolu_42"),
            ],
        )
        sdk_class, _ = _install_sdk_mock(response)
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            result = await client.send_message(messages=[_user_msg()])
        assert len(result.tool_calls) == 1
        parsed = result.tool_calls[0]
        assert parsed.name == "move"
        assert parsed.arguments == {"direction": "north"}
        assert parsed.call_id == "toolu_42"

    @allure.story("send_message")
    @allure.title("AnthropicClient.send_message omits the system kwarg when the system_prompt is empty")
    @pytest.mark.asyncio
    async def test_send_message_no_system(self) -> None:
        sdk_class, create_mock = _install_sdk_mock()
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            await client.send_message(messages=[_user_msg()])
        assert "system" not in create_mock.call_args.kwargs

    @allure.story("send_message")
    @allure.title("AnthropicClient.send_message forwards temperature and max_tokens overrides to the SDK call")
    @pytest.mark.asyncio
    async def test_send_message_overrides(self) -> None:
        sdk_class, create_mock = _install_sdk_mock()
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            await client.send_message(
                messages=[_user_msg()],
                temperature=0.25,
                max_tokens=128,
            )
        kwargs = create_mock.call_args.kwargs
        assert kwargs["temperature"] == pytest.approx(0.25)
        assert kwargs["max_tokens"] == 128

    @allure.story("Strict structured outputs")
    @allure.title(
        "AnthropicClient.send_message routes through beta.messages.create with output_format "
        "when a json_schema is supplied",
    )
    @pytest.mark.asyncio
    async def test_send_message_json_schema_uses_beta_endpoint(self) -> None:
        sdk_class, beta_create = _install_beta_sdk_mock()
        widget_schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            await client.send_message(
                messages=[_user_msg()],
                output_format=OutputFormat(schema=widget_schema, schema_name="Widget"),
            )
        kwargs = beta_create.call_args.kwargs
        wired_schema = kwargs["output_format"]["schema"]
        assert kwargs["output_format"]["type"] == "json_schema"
        assert wired_schema["additionalProperties"] is False
        assert wired_schema["properties"] == widget_schema["properties"]
        assert kwargs["model"] == _MODEL

    @allure.story("Strict structured outputs")
    @allure.title(
        "AnthropicClient.send_message stamps additionalProperties: false on nested object schemas "
        "without mutating the caller's dict",
    )
    @pytest.mark.asyncio
    async def test_send_message_json_schema_hardens_nested_objects(self) -> None:
        sdk_class, beta_create = _install_beta_sdk_mock()
        nested_node: dict[str, Any] = {"type": "object", "properties": {"k": {"type": "string"}}}
        original_schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "nested": nested_node,
                "items": {"type": "array", "items": {"type": "object", "properties": {}}},
            },
            "$defs": {
                "Inner": {"type": "object", "properties": {"x": {"type": "integer"}}},
            },
        }
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            await client.send_message(
                messages=[_user_msg()],
                output_format=OutputFormat(schema=original_schema, schema_name="Nested"),
            )
        wired_schema = beta_create.call_args.kwargs["output_format"]["schema"]
        assert wired_schema["additionalProperties"] is False
        assert wired_schema["properties"]["nested"]["additionalProperties"] is False
        assert wired_schema["properties"]["items"]["items"]["additionalProperties"] is False
        assert wired_schema["$defs"]["Inner"]["additionalProperties"] is False
        # Caller's dicts must remain untouched.
        assert "additionalProperties" not in original_schema
        assert "additionalProperties" not in nested_node

    @allure.story("Strict structured outputs")
    @allure.title(
        "AnthropicClient.send_message strips minimum/maximum from integer schema nodes "
        "(Anthropic beta rejects them with invalid_request_error)",
    )
    @pytest.mark.asyncio
    async def test_send_message_json_schema_strips_integer_range(self) -> None:
        sdk_class, beta_create = _install_beta_sdk_mock()
        integer_node: dict[str, Any] = {
            "type": "integer",
            "minimum": 0,
            "maximum": 10,
            "exclusiveMinimum": -1,
            "exclusiveMaximum": 11,
        }
        original_schema: dict[str, Any] = {
            "type": "object",
            "properties": {"score": integer_node},
        }
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            await client.send_message(
                messages=[_user_msg()],
                output_format=OutputFormat(schema=original_schema, schema_name="Scored"),
            )
        wired_schema = beta_create.call_args.kwargs["output_format"]["schema"]
        assert wired_schema["properties"]["score"] == {"type": "integer"}
        assert integer_node["minimum"] == 0
        assert integer_node["maximum"] == 10

    @allure.story("Strict structured outputs")
    @allure.title(
        "AnthropicClient.send_message translates 'Schema is too complex' 400 into "
        "NotImplementedError and quarantines the schema for subsequent calls",
    )
    @pytest.mark.asyncio
    async def test_send_message_schema_too_complex_falls_back(self) -> None:
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        response = httpx.Response(400, request=request)
        too_complex = BadRequestError(
            "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
            "'message': 'Schema is too complex.'}}",
            response=response,
            body=None,
        )
        sdk_class, beta_create = _install_beta_sdk_mock(side_effect=too_complex)
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            schema = {"type": "object", "properties": {"x": {"type": "string"}}}
            with pytest.raises(NotImplementedError, match="too complex"):
                await client.send_message(
                    messages=[_user_msg()],
                    output_format=OutputFormat(schema=schema, schema_name="BigSchema"),
                )
            # Second call with the same schema_name skips the strict path
            # entirely — no second beta roundtrip.
            beta_create.reset_mock()
            with pytest.raises(NotImplementedError, match="previously rejected"):
                await client.send_message(
                    messages=[_user_msg()],
                    output_format=OutputFormat(schema=schema, schema_name="BigSchema"),
                )
            beta_create.assert_not_called()

    @allure.story("Strict structured outputs")
    @allure.title(
        "AnthropicClient.send_message lets non-complexity 400s propagate as BadRequestError "
        "so genuine API failures are not silently downgraded",
    )
    @pytest.mark.asyncio
    async def test_send_message_other_400_propagates(self) -> None:
        sdk_class, _ = _install_beta_sdk_mock(side_effect=_make_anthropic_400())
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            with pytest.raises(BadRequestError):
                await client.send_message(
                    messages=[_user_msg()],
                    output_format=OutputFormat(
                        schema={"type": "object", "properties": {}},
                        schema_name="Widget",
                    ),
                )

    @allure.story("Strict structured outputs")
    @allure.title(
        "AnthropicClient.send_message strips noise metadata (title/description/default/examples) "
        "to keep below the beta complexity budget while preserving property names that collide with those keys",
    )
    @pytest.mark.asyncio
    async def test_send_message_json_schema_strips_noise_keys(self) -> None:
        sdk_class, beta_create = _install_beta_sdk_mock()
        original_schema: dict[str, Any] = {
            "title": "Goal",
            "description": "Top-level description",
            "type": "object",
            "properties": {
                # ``description`` here is a property name, not metadata — must survive.
                "description": {"type": "string", "title": "Goal description"},
                "kind": {"type": "string", "default": "kill", "examples": ["kill", "flee"]},
            },
        }
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            await client.send_message(
                messages=[_user_msg()],
                output_format=OutputFormat(schema=original_schema, schema_name="Goal"),
            )
        wired_schema = beta_create.call_args.kwargs["output_format"]["schema"]
        assert "title" not in wired_schema
        assert "description" not in wired_schema  # top-level metadata stripped
        assert "description" in wired_schema["properties"]  # property name kept
        assert wired_schema["properties"]["description"] == {"type": "string"}
        assert wired_schema["properties"]["kind"] == {"type": "string"}

    @allure.story("Retry on 5xx")
    @allure.title(
        "AnthropicClient.send_message retries beta endpoint on Anthropic 5xx and returns the eventual success"
    )
    @pytest.mark.asyncio
    async def test_send_message_retries_5xx_then_succeeds(self) -> None:
        sdk_class = MagicMock()
        sdk_instance = MagicMock()
        beta_create = AsyncMock(side_effect=[_make_anthropic_5xx(), _make_anthropic_5xx(), _make_response()])
        sdk_instance.beta.messages.create = beta_create
        sdk_class.return_value = sdk_instance
        with (
            patch(_ANTHROPIC_CTOR, sdk_class),
            patch("llm.anthropic_client.asyncio.sleep", new=AsyncMock()) as sleep_mock,
        ):
            client = AnthropicClient(model=_MODEL, api_key="k")
            result = await client.send_message(
                messages=[_user_msg()],
                output_format=OutputFormat(schema={"type": "object", "properties": {}}, schema_name="Widget"),
            )
        assert beta_create.await_count == 3
        assert result.body == "hello"
        # Backoff schedule: 2.0s, 4.0s
        assert [call.args[0] for call in sleep_mock.await_args_list] == [pytest.approx(2.0), pytest.approx(4.0)]

    @allure.story("Retry on 5xx")
    @allure.title("AnthropicClient.send_message stops retrying after _RETRY_MAX_ATTEMPTS and raises the last 5xx")
    @pytest.mark.asyncio
    async def test_send_message_5xx_exhausts_retries(self) -> None:
        sdk_class = MagicMock()
        sdk_instance = MagicMock()
        final_error = _make_anthropic_5xx("final")
        beta_create = AsyncMock(side_effect=[_make_anthropic_5xx(), _make_anthropic_5xx(), final_error])
        sdk_instance.beta.messages.create = beta_create
        sdk_class.return_value = sdk_instance
        with patch(_ANTHROPIC_CTOR, sdk_class), patch("llm.anthropic_client.asyncio.sleep", new=AsyncMock()):
            client = AnthropicClient(model=_MODEL, api_key="k")
            with pytest.raises(InternalServerError) as exc_info:
                await client.send_message(
                    messages=[_user_msg()],
                    output_format=OutputFormat(schema={"type": "object", "properties": {}}, schema_name="Widget"),
                )
        assert beta_create.await_count == 3
        assert exc_info.value is final_error

    @allure.story("Retry on 5xx")
    @allure.title("_call_with_retry does not retry 4xx errors and propagates them on the first attempt")
    @pytest.mark.asyncio
    async def test_call_with_retry_does_not_retry_4xx(self) -> None:
        bad = _make_anthropic_400()
        create = AsyncMock(side_effect=bad)
        sleep_mock = AsyncMock()
        with patch("llm.anthropic_client.asyncio.sleep", new=sleep_mock):
            with pytest.raises(BadRequestError):
                await _call_with_retry(create)
        assert create.await_count == 1
        sleep_mock.assert_not_awaited()

    @allure.story("Strict structured outputs")
    @allure.title("AnthropicClient.send_message preserves an explicit additionalProperties: true setting")
    @pytest.mark.asyncio
    async def test_send_message_json_schema_preserves_explicit_additional_properties(self) -> None:
        sdk_class, beta_create = _install_beta_sdk_mock()
        permissive_schema = {
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "additionalProperties": True,
        }
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            await client.send_message(
                messages=[_user_msg()],
                output_format=OutputFormat(schema=permissive_schema, schema_name="Permissive"),
            )
        wired_schema = beta_create.call_args.kwargs["output_format"]["schema"]
        assert wired_schema["additionalProperties"] is True

    @allure.story("Strict structured outputs")
    @allure.title(
        "AnthropicClient.send_message raises NotImplementedError immediately "
        "when supports_structured_output is False, without calling the API",
    )
    @pytest.mark.asyncio
    async def test_send_message_json_schema_unsupported_flag_raises_immediately(self) -> None:
        sdk_class, beta_create = _install_beta_sdk_mock()
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k", supports_structured_output=False)
            with pytest.raises(NotImplementedError, match=_MODEL):
                await client.send_message(
                    messages=[_user_msg()],
                    output_format=OutputFormat(
                        schema={"type": "object", "properties": {}},
                        schema_name="Widget",
                    ),
                )
        beta_create.assert_not_called()

    @allure.story("Strict structured outputs")
    @allure.title("AnthropicClient.send_message lets beta API errors propagate without translation")
    @pytest.mark.asyncio
    async def test_send_message_json_schema_api_error_propagates_unchanged(self) -> None:
        error = RuntimeError("upstream failure")
        sdk_class, _ = _install_beta_sdk_mock(side_effect=error)
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            with pytest.raises(RuntimeError, match="upstream failure"):
                await client.send_message(
                    messages=[_user_msg()],
                    output_format=OutputFormat(
                        schema={"type": "object", "properties": {}},
                        schema_name="Widget",
                    ),
                )

    @allure.story("Message formatting")
    @allure.title("AnthropicClient._format_messages maps Role.USER to 'user' and Role.ASSISTANT to 'assistant'")
    def test_format_messages_role_mapping(self) -> None:
        sdk_class, _ = _install_sdk_mock()
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            formatted = client._format_messages(
                [
                    msg.Message(role=msg.Role.USER, body="u"),
                    msg.Message(role=msg.Role.ASSISTANT, body="a"),
                ],
            )
        assert formatted == [
            {"role": "user", "content": "u"},
            {"role": "assistant", "content": "a"},
        ]

    @allure.story("Message formatting")
    @allure.title("AnthropicClient._format_messages maps Role.SYSTEM to 'assistant' (documented current behavior)")
    def test_format_messages_system_role_maps_to_assistant(self) -> None:
        sdk_class, _ = _install_sdk_mock()
        with patch(_ANTHROPIC_CTOR, sdk_class):
            client = AnthropicClient(model=_MODEL, api_key="k")
            formatted = client._format_messages(
                [msg.Message(role=msg.Role.SYSTEM, body="s")],
            )
        assert formatted == [{"role": "assistant", "content": "s"}]
