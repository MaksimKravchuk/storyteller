"""Regression tests for performer response schemas under OpenAI strict mode."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import NamedTuple

import allure
import pytest
from pydantic import BaseModel

from cast import schemas as schemas_pkg
from llm.openai_client import _StrictSchemaNormalizer


class _ResponseModel(NamedTuple):
    name: str
    model: type[BaseModel]


def _is_local_pydantic_model(module_name: str, obj: object) -> bool:
    if not inspect.isclass(obj):
        return False
    if not issubclass(obj, BaseModel) or obj is BaseModel:
        return False
    return obj.__module__ == module_name


def _discover_response_models() -> list[_ResponseModel]:
    """Return every Pydantic model defined under ``cast.schemas``.

    Auto-discovery so a new schema added tomorrow is covered without
    anyone remembering to wire it into the parametrization.
    """
    discovered: dict[str, type[BaseModel]] = {}
    for module_info in pkgutil.iter_modules(schemas_pkg.__path__):
        module = importlib.import_module(f"{schemas_pkg.__name__}.{module_info.name}")
        for attr_name, attr_value in inspect.getmembers(module):
            if _is_local_pydantic_model(module.__name__, attr_value):
                discovered[attr_name] = attr_value
    return [_ResponseModel(name=name, model=model) for name, model in sorted(discovered.items())]


def _object_is_non_strict(node: dict) -> bool:
    """Return True when this node is a ``type: object`` that strict mode rejects."""
    return node.get("type") == "object" and node.get("additionalProperties") is not False


def _walk(node: object, path: str, violations: list[str]) -> None:
    """Accumulate the paths of every node that fails strict-mode validation."""
    if isinstance(node, dict):
        if _object_is_non_strict(node):
            violations.append(path)
        for key, child in node.items():
            _walk(child, f"{path}.{key}", violations)
    elif isinstance(node, list):
        for index, child in enumerate(node):
            _walk(child, f"{path}[{index}]", violations)


def _strict_violations(response: _ResponseModel) -> list[str]:
    wrapped = _StrictSchemaNormalizer.wrap(response.model.model_json_schema(), response.name)
    violations: list[str] = []
    _walk(wrapped["json_schema"]["schema"], "$", violations)
    return violations


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("OpenAI client — strict schema regression")
@allure.story("Performer response schemas are strict-mode compatible")
@allure.title("{response.name} wrapped schema carries no free-form object node")
@pytest.mark.parametrize(
    "response",
    _discover_response_models(),
    ids=lambda response: response.name,
)
def test_performer_response_has_no_free_form_object(response: _ResponseModel) -> None:
    violations = _strict_violations(response)
    assert violations == [], (
        "Every type=object node must set additionalProperties=false for OpenAI strict mode; "
        f"offending paths in {response.name}: {violations}"
    )
