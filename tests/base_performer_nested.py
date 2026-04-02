"""Performer stubs for nested-execution and context-capture tests."""

from __future__ import annotations

from typing import Any

from cast.base_performer_class import BasePerformer
from tests.base_performer_helpers import EMPTY_PROMPT, StackRecorder, make_mock


class OuterDelegator(BasePerformer):
    """Delegates to a StackRecorder to test nested stack ordering."""

    def __init__(self, target: list[str]):
        super().__init__(llm_client=make_mock(), system_prompt_template=EMPTY_PROMPT)
        self._inner = StackRecorder(target=target)

    async def act(self, input_data: Any, context: Any) -> Any:
        return await self._inner.execute(input_data)


class InnerRaiser(BasePerformer):
    """Always raises ``ValueError`` from ``act``."""

    async def act(self, input_data: Any, context: Any) -> None:
        raise ValueError("inner boom")


class OuterCatcher(BasePerformer):
    """Delegates to InnerRaiser, catches the ValueError."""

    async def act(self, input_data: Any, context: Any) -> Any:
        inner = InnerRaiser(llm_client=make_mock(), system_prompt_template=EMPTY_PROMPT)
        try:
            await inner.execute(input_data)
        except ValueError:
            return None
        return "unexpected"


class ContextCapture(BasePerformer):
    """Stores the context dict passed to ``act``."""

    def __init__(self, received: dict):
        super().__init__(llm_client=make_mock(), system_prompt_template=EMPTY_PROMPT)
        self._received = received

    async def act(self, input_data: Any, context: Any) -> str:
        self._received.update(context)
        return "ok"


class ContextRawCapture(BasePerformer):
    """Stores the raw context object in a holder dict."""

    def __init__(self, holder: dict):
        super().__init__(llm_client=make_mock(), system_prompt_template=EMPTY_PROMPT)
        self._holder = holder

    async def act(self, input_data: Any, context: Any) -> str:
        self._holder["ctx"] = context
        return "ok"
