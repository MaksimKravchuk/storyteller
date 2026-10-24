"""Tests for llm.openai_client.OpenAIClient — SDK wiring, payload, streaming, formatting."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from llm import message as msg
from llm.base_client import OutputFormat
from llm.openai_client import OpenAIClient, _StrictSchemaNormalizer
from llm.message import Tool


def _to_strict_schema(schema: dict, name: str) -> dict:
    """Thin shim so tests can keep using a function-level call."""
    return _StrictSchemaNormalizer.wrap(schema, name)


_OPENAI_CTOR = "openai.AsyncOpenAI"
_MODEL = "gpt-4"
_JSON_MODE_TYPE = "json_object"


def _make_response(
    content: str | None = "hello",
    prompt_tokens: int = 11,
    completion_tokens: int = 3,
    model: str = _MODEL,
) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
        model=model,
    )


def _install_sdk_mock(response: SimpleNamespace | None = None) -> tuple[MagicMock, AsyncMock]:
    """Patch AsyncOpenAI; return (sdk_class_mock, create_mock)."""
    sdk_class = MagicMock()
    sdk_instance = MagicMock()
    payload = _make_response() if response is None else response
    create_mock = AsyncMock(return_value=payload)
    sdk_instance.chat.completions.create = create_mock
    sdk_class.return_value = sdk_instance
    return sdk_class, create_mock


def _user_msg(body: str = "hi") -> msg.Message:
    return msg.Message(role=msg.Role.USER, body=body)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("OpenAI client")
class TestOpenAIClient:
    @allure.story("Constructor")
    @allure.title("OpenAIClient instantiates AsyncOpenAI with the supplied api_key on construction")
    def test_constructor_wires_sdk(self) -> None:
        sdk_class, _ = _install_sdk_mock()
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="sk-xyz")
        sdk_class.assert_called_once_with(api_key="sk-xyz", timeout=120, max_retries=0)
        assert client.model == _MODEL

    @allure.story("send_message")
    @allure.title("OpenAIClient.send_message builds a chat completion payload with model, messages, and token cap")
    @pytest.mark.asyncio
    async def test_send_message_payload(self) -> None:
        sdk_class, create_mock = _install_sdk_mock()
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="k")
            result = await client.send_message(messages=[_user_msg()], system_prompt="sys")

        kwargs = create_mock.call_args.kwargs
        assert kwargs["model"] == _MODEL
        assert kwargs["temperature"] == pytest.approx(0.7)
        assert kwargs["max_completion_tokens"] == 2048
        assert kwargs["messages"][0] == {"role": "system", "content": "sys"}
        assert kwargs["messages"][1] == {"role": "user", "content": "hi"}
        assert "response_format" not in kwargs
        assert result.body == "hello"
        assert result.usage == {"prompt_tokens": 11, "completion_tokens": 3}
        assert result.model == _MODEL

    @allure.story("send_message")
    @allure.title("OpenAIClient.send_message forwards temperature and max_tokens overrides to the SDK call")
    @pytest.mark.asyncio
    async def test_send_message_overrides(self) -> None:
        sdk_class, create_mock = _install_sdk_mock()
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="k")
            await client.send_message(messages=[_user_msg()], temperature=0.25, max_tokens=64)
        kwargs = create_mock.call_args.kwargs
        assert kwargs["temperature"] == pytest.approx(0.25)
        assert kwargs["max_completion_tokens"] == 64

    @allure.story("send_message")
    @allure.title("OpenAIClient.send_message passes response_format when the caller requests JSON mode")
    @pytest.mark.asyncio
    async def test_send_message_response_format(self) -> None:
        sdk_class, create_mock = _install_sdk_mock()
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="k")
            await client.send_message(
                messages=[_user_msg()],
                output_format=OutputFormat(response_format={"type": _JSON_MODE_TYPE}),
            )
        assert create_mock.call_args.kwargs["response_format"] == {"type": _JSON_MODE_TYPE}

    @allure.story("Strict structured outputs")
    @allure.title(
        "OpenAIClient.send_message wraps a strict OutputFormat schema into the response_format "
        "envelope and names it after the supplied schema_name",
    )
    @pytest.mark.asyncio
    async def test_send_message_json_schema_wraps_response_format(self) -> None:
        sdk_class, create_mock = _install_sdk_mock()
        widget_schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
                "label": {"type": "string", "default": "x"},
            },
            "required": ["count"],
        }
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="k")
            await client.send_message(
                messages=[_user_msg()],
                output_format=OutputFormat(schema=widget_schema, schema_name="WidgetResponse"),
            )
        wrapped = create_mock.call_args.kwargs["response_format"]
        assert wrapped["type"] == "json_schema"
        assert wrapped["json_schema"]["name"] == "WidgetResponse"
        assert wrapped["json_schema"]["strict"] is True
        normalized = wrapped["json_schema"]["schema"]
        assert normalized["additionalProperties"] is False
        assert normalized["required"] == ["count", "label"]
        assert "default" not in normalized["properties"]["label"]

    @allure.story("Strict structured outputs")
    @allure.title(
        "OpenAIClient.send_message prefers a strict schema over response_format when both are set on the OutputFormat",
    )
    @pytest.mark.asyncio
    async def test_send_message_json_schema_overrides_response_format(self) -> None:
        sdk_class, create_mock = _install_sdk_mock()
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="k")
            await client.send_message(
                messages=[_user_msg()],
                output_format=OutputFormat(
                    response_format={"type": _JSON_MODE_TYPE},
                    schema={"type": "object", "properties": {"x": {"type": "string"}}},
                    schema_name="Widget",
                ),
            )
        assert create_mock.call_args.kwargs["response_format"]["type"] == "json_schema"

    @allure.story("Strict structured outputs")
    @allure.title("OpenAIClient.send_message defaults the schema name to 'Response' when schema_name is omitted")
    @pytest.mark.asyncio
    async def test_send_message_json_schema_defaults_name(self) -> None:
        sdk_class, create_mock = _install_sdk_mock()
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="k")
            await client.send_message(
                messages=[_user_msg()],
                output_format=OutputFormat(schema={"type": "object", "properties": {}}),
            )
        wrapped = create_mock.call_args.kwargs["response_format"]
        assert wrapped["json_schema"]["name"] == "Response"

    @allure.story("Tool calls")
    @allure.title("OpenAIClient.send_message serialises tools into the chat completion payload")
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
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="k")
            await client.send_message(
                messages=[_user_msg()],
                output_format=OutputFormat(tools=(tool,), tool_choice="required"),
            )
        kwargs = create_mock.call_args.kwargs
        assert kwargs["tool_choice"] == "required"
        wire_tools = kwargs["tools"]
        assert len(wire_tools) == 1
        wire_tool = wire_tools[0]
        assert wire_tool["type"] == "function"
        assert wire_tool["function"]["name"] == "move"
        assert wire_tool["function"]["strict"] is True
        # Strict-validator normalisation must have been applied to parameters.
        assert wire_tool["function"]["parameters"]["additionalProperties"] is False

    @allure.story("Tool calls")
    @allure.title("OpenAIClient.send_message maps a tool name in tool_choice to the OpenAI dict shape")
    @pytest.mark.asyncio
    async def test_tool_choice_by_name(self) -> None:
        sdk_class, create_mock = _install_sdk_mock()
        tool = Tool(
            name="talk",
            description="Player talks.",
            parameters_schema={"type": "object", "properties": {}},
        )
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="k")
            await client.send_message(
                messages=[_user_msg()],
                output_format=OutputFormat(tools=(tool,), tool_choice="talk"),
            )
        assert create_mock.call_args.kwargs["tool_choice"] == {
            "type": "function",
            "function": {"name": "talk"},
        }

    @allure.story("Tool calls")
    @allure.title("OpenAIClient.send_message parses tool_calls from the response, decoding JSON arguments")
    @pytest.mark.asyncio
    async def test_send_message_parses_tool_calls(self) -> None:
        tool_call_obj = SimpleNamespace(
            id="call_123",
            function=SimpleNamespace(
                name="move",
                arguments='{"direction": "north"}',
            ),
        )
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=None, tool_calls=[tool_call_obj]),
                ),
            ],
            usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2),
            model=_MODEL,
        )
        sdk_class, _ = _install_sdk_mock(response)
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="k")
            result = await client.send_message(messages=[_user_msg()])
        assert len(result.tool_calls) == 1
        parsed = result.tool_calls[0]
        assert parsed.name == "move"
        assert parsed.arguments == {"direction": "north"}
        assert parsed.call_id == "call_123"

    @allure.story("send_message")
    @allure.title("OpenAIClient.send_message returns an empty body and zeroed usage when the SDK response is blank")
    @pytest.mark.asyncio
    async def test_send_message_empty_response(self) -> None:
        blank = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None))],
            usage=None,
            model=_MODEL,
        )
        sdk_class, _ = _install_sdk_mock(blank)
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="k")
            result = await client.send_message(messages=[_user_msg("x")])
        assert result.body == ""
        assert result.usage == {"prompt_tokens": 0, "completion_tokens": 0}

    @allure.story("Message formatting")
    @allure.title("OpenAIClient._format_messages omits the system role when the system_prompt is empty")
    def test_format_messages_omits_empty_system(self) -> None:
        sdk_class, _ = _install_sdk_mock()
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="k")
            formatted = client._format_messages([_user_msg()], system_prompt="")
        assert formatted == [{"role": "user", "content": "hi"}]

    @allure.story("Message formatting")
    @allure.title("OpenAIClient._format_messages sanitizes message bodies so null bytes do not reach the SDK")
    def test_format_messages_sanitizes_bodies(self) -> None:
        sdk_class, _ = _install_sdk_mock()
        with patch(_OPENAI_CTOR, sdk_class):
            client = OpenAIClient(model=_MODEL, api_key="k")
            formatted = client._format_messages(
                [_user_msg("hel\x00lo")],
                system_prompt="sy\x00s",
            )
        assert formatted[0] == {"role": "system", "content": "sys"}
        assert formatted[1] == {"role": "user", "content": "hello"}

    @allure.story("send_message")
    @allure.title("OpenAIClient.send_message logs the API error body and re-raises on a 400 Bad Request")
    @pytest.mark.asyncio
    async def test_send_message_api_error_is_logged_and_reraised(self) -> None:
        """A 400 Bad Request must be logged with the OpenAI error body, then re-raised.

        Regression test for the debuggability gap where an ``httpx.HTTPStatusError``
        was bubbling up to the caller without the OpenAI error message in the logs.
        """
        import httpx
        from loguru import logger
        from openai import BadRequestError

        error_body = {
            "error": {
                "message": "response_format of type 'json_object' is not supported with this model",
                "type": "invalid_request_error",
            },
        }
        fake_response = httpx.Response(
            status_code=400,
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        )
        bad_request = BadRequestError(
            message="400 Bad Request",
            response=fake_response,
            body=error_body,
        )

        sdk_class = MagicMock()
        sdk_instance = MagicMock()
        sdk_instance.chat.completions.create = AsyncMock(side_effect=bad_request)
        sdk_class.return_value = sdk_instance

        captured: list[str] = []
        sink_id = logger.add(lambda record: captured.append(str(record)), level="ERROR")
        try:
            with patch(_OPENAI_CTOR, sdk_class):
                client = OpenAIClient(model=_MODEL, api_key="k")
                with pytest.raises(BadRequestError):
                    await client.send_message(
                        messages=[_user_msg("trigger 400")],
                        system_prompt="director system prompt",
                        output_format=OutputFormat(response_format={"type": _JSON_MODE_TYPE}),
                    )
        finally:
            logger.remove(sink_id)

        assert any("OpenAI API error" in entry for entry in captured)
        assert any(_MODEL in entry for entry in captured)
        assert any("json_object" in entry for entry in captured)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("OpenAI client — strict schema normalizer")
class TestToStrictSchema:
    @allure.story("Object normalization")
    @allure.title(
        "_to_strict_schema sets additionalProperties=false and lists every property as required",
    )
    def test_object_node_is_normalized(self) -> None:
        schema = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
            "required": ["a"],
        }
        wrapped = _to_strict_schema(schema, "Widget")
        normalized = wrapped["json_schema"]["schema"]
        assert normalized["additionalProperties"] is False
        assert normalized["required"] == ["a", "b"]

    @allure.story("Defaults")
    @allure.title("_to_strict_schema strips default keys from every nested property")
    def test_defaults_are_stripped(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "scope": {"type": "string", "default": "remote", "enum": ["local", "remote"]},
                "label": {"type": "string", "default": ""},
            },
        }
        normalized = _to_strict_schema(schema, "Widget")["json_schema"]["schema"]
        assert "default" not in normalized["properties"]["scope"]
        assert "default" not in normalized["properties"]["label"]

    @allure.story("Recursion")
    @allure.title("_to_strict_schema recurses into array items, $defs, and anyOf composites")
    def test_recurses_into_items_defs_and_anyof(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"name": {"type": "string", "default": "x"}},
                    },
                },
                "either": {
                    "anyOf": [
                        {"type": "object", "properties": {"k": {"type": "integer"}}},
                        {"type": "null"},
                    ],
                },
            },
            "$defs": {
                "Nested": {
                    "type": "object",
                    "properties": {"x": {"type": "string", "default": "y"}},
                },
            },
        }
        normalized = _to_strict_schema(schema, "Widget")["json_schema"]["schema"]
        item = normalized["properties"]["items"]["items"]
        assert item["additionalProperties"] is False
        assert item["required"] == ["name"]
        assert "default" not in item["properties"]["name"]
        either_obj = normalized["properties"]["either"]["anyOf"][0]
        assert either_obj["additionalProperties"] is False
        nested = normalized["$defs"]["Nested"]
        assert nested["additionalProperties"] is False
        assert nested["required"] == ["x"]
        assert "default" not in nested["properties"]["x"]

    @allure.story("Caller isolation")
    @allure.title("_to_strict_schema does not mutate the caller's schema dict")
    def test_caller_schema_is_not_mutated(self) -> None:
        property_a: dict[str, object] = {"type": "string", "default": "x"}
        schema: dict[str, object] = {
            "type": "object",
            "properties": {"a": property_a},
            "required": ["a"],
        }
        _to_strict_schema(schema, "Widget")
        assert "additionalProperties" not in schema
        assert property_a["default"] == "x"
