"""Tests for llm.base_client.BaseLLMClient — constructor defaults and abstract contract."""

from __future__ import annotations

from typing import Any

import allure
import pytest

from llm.base_client import BaseLLMClient, OutputFormat
from llm.message import LLMResponse, Message


class _StubClient(BaseLLMClient):
    """Minimal concrete subclass used to exercise the base constructor."""

    def __init__(self, model: str, **kwargs: Any) -> None:
        super().__init__(model=model, **kwargs)
        self.last_send_kwargs: dict[str, Any] = {}

    async def send_message(
        self,
        messages: list[Message],
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        output_format: OutputFormat | None = None,
    ) -> LLMResponse:
        self.last_send_kwargs = {
            "messages": messages,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "output_format": output_format,
        }
        return LLMResponse(body="")


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("BaseLLMClient")
class TestBaseLLMClient:
    @allure.story("Constructor")
    @allure.title("BaseLLMClient stores the model and api_key arguments on the instance")
    def test_stores_model_and_api_key(self) -> None:
        client = _StubClient(model="m-1", api_key="sk-abc")
        assert client.model == "m-1"
        assert client.api_key == "sk-abc"

    @allure.story("Constructor")
    @allure.title("BaseLLMClient uses a default temperature of 0.7 and max_tokens of 2048 when not supplied")
    def test_default_temperature_and_max_tokens(self) -> None:
        client = _StubClient(model="m-1")
        assert client.temperature == pytest.approx(0.7)
        assert client.max_tokens == 2048

    @allure.story("Constructor")
    @allure.title("BaseLLMClient accepts explicit temperature and max_tokens overrides")
    def test_overrides_accepted(self) -> None:
        client = _StubClient(model="m-1", temperature=0.25, max_tokens=42)
        assert client.temperature == pytest.approx(0.25)
        assert client.max_tokens == 42

    @allure.story("Constructor")
    @allure.title("BaseLLMClient defaults api_key to None when no argument is passed")
    def test_api_key_default_none(self) -> None:
        client = _StubClient(model="m-1")
        assert client.api_key is None

    @allure.story("Abstract contract")
    @allure.title("BaseLLMClient cannot be instantiated directly because it has abstract methods")
    def test_cannot_instantiate_abstract_base(self) -> None:
        with pytest.raises(TypeError):
            BaseLLMClient(model="m-1")  # type: ignore[abstract]

    @allure.story("Abstract contract")
    @allure.title(
        "BaseLLMClient.send_message accepts an OutputFormat carrying schema and schema_name "
        "for strict structured outputs",
    )
    @pytest.mark.asyncio
    async def test_send_message_signature_accepts_output_format(self) -> None:
        client = _StubClient(model="m-1")
        of = OutputFormat(
            schema={"type": "object", "properties": {}},
            schema_name="WidgetResponse",
        )
        await client.send_message(messages=[], output_format=of)
        captured = client.last_send_kwargs["output_format"]
        assert captured.is_strict is True
        assert captured.schema == {"type": "object", "properties": {}}
        assert captured.schema_name == "WidgetResponse"
