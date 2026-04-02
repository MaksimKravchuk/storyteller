"""Reusable BasePerformer stubs shared by test_base_performer* modules."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from cast.base_performer_class import BasePerformer
from llm.call_logger import agent_stack
from prompts.base_template import PromptTemplate

EMPTY_PROMPT = PromptTemplate([])


def make_mock() -> MagicMock:
    """Create a fresh MagicMock for the llm_client parameter."""
    return MagicMock()


def get_stack() -> list[str]:
    """Return the current agent stack or an empty list."""
    return agent_stack.get(None) or []


class OKPerformer(BasePerformer):
    """Returns a canned string from ``act``."""

    def __init__(self, act_output: str = "ok"):
        super().__init__(llm_client=make_mock(), system_prompt_template=EMPTY_PROMPT)
        self._act_output = act_output

    async def act(self, input_data: Any, context: Any) -> str:
        return self._act_output


class RaisingPerformer(BasePerformer):
    """Raises the given exception from ``act``."""

    def __init__(self, exc: Exception):
        super().__init__(llm_client=make_mock(), system_prompt_template=EMPTY_PROMPT)
        self._exc = exc

    async def act(self, input_data: Any, context: Any) -> None:
        raise self._exc


class StackRecorder(BasePerformer):
    """Appends current agent_stack to a shared list during ``act``."""

    def __init__(self, target: list[str]):
        super().__init__(llm_client=make_mock(), system_prompt_template=EMPTY_PROMPT)
        self._target = target

    async def act(self, input_data: Any, context: Any) -> None:
        self._target.extend(get_stack())
