"""Regression tests for performer response schemas under OpenAI strict mode."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Callable, NamedTuple

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


def _has_pydantic_uuid4_format(node: dict) -> bool:
    """Return True when this node still carries pydantic's non-standard ``format: "uuid4"``."""
    return node.get("format") == "uuid4"


def _collect_paths(node: object, path: str, hits: list[str], predicate: Callable[[dict], bool]) -> None:
    """Walk *node* and append every path where *predicate(dict-node)* is True."""
    if isinstance(node, dict):
        if predicate(node):
            hits.append(path)
        for key, child in node.items():
            _collect_paths(child, f"{path}.{key}", hits, predicate)
    elif isinstance(node, list):
        for index, child in enumerate(node):
            _collect_paths(child, f"{path}[{index}]", hits, predicate)


def _wrapped_schema(response: _ResponseModel) -> dict:
    wrapped = _StrictSchemaNormalizer.wrap(response.model.model_json_schema(), response.name)
    return wrapped["json_schema"]["schema"]


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
    violations: list[str] = []
    _collect_paths(_wrapped_schema(response), "$", violations, _object_is_non_strict)
    assert violations == [], (
        "Every type=object node must set additionalProperties=false for OpenAI strict mode; "
        f"offending paths in {response.name}: {violations}"
    )


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("OpenAI client — strict schema regression")
@allure.story("Performer response schemas are strict-mode compatible")
@allure.title("{response.name} wrapped schema rewrites pydantic's UUID4 format to standard uuid")
@pytest.mark.parametrize(
    "response",
    _discover_response_models(),
    ids=lambda response: response.name,
)
def test_performer_response_has_no_pydantic_uuid4_format(response: _ResponseModel) -> None:
    hits: list[str] = []
    _collect_paths(_wrapped_schema(response), "$", hits, _has_pydantic_uuid4_format)
    assert hits == [], (
        "Pydantic emits format='uuid4' for UUID4 fields, but OpenAI strict mode "
        f"only accepts the standard 'uuid'; offending paths in {response.name}: {hits}"
    )
