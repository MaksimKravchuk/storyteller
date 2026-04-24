"""Regression tests for performer response schemas under OpenAI strict mode."""

from __future__ import annotations

import allure
import pytest
from pydantic import BaseModel

from cast.schemas.npc_response import NPCResponse
from cast.schemas.scene_response import SceneResponse
from llm.openai_client import _StrictSchemaNormalizer


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


def _strict_violations(schema_cls: type[BaseModel], schema_name: str) -> list[str]:
    wrapped = _StrictSchemaNormalizer.wrap(schema_cls.model_json_schema(), schema_name)
    violations: list[str] = []
    _walk(wrapped["json_schema"]["schema"], "$", violations)
    return violations


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("OpenAI client — strict schema regression")
@allure.story("Performer response schemas are strict-mode compatible")
@allure.title("{schema_name} wrapped schema carries no free-form object node")
@pytest.mark.parametrize(
    ("schema_cls", "schema_name"),
    [
        (NPCResponse, "NPCResponse"),
        (SceneResponse, "SceneResponse"),
    ],
)
def test_performer_response_has_no_free_form_object(
    schema_cls: type[BaseModel],
    schema_name: str,
) -> None:
    violations = _strict_violations(schema_cls, schema_name)
    assert violations == [], (
        "Every type=object node must set additionalProperties=false for OpenAI strict mode; "
        f"offending paths in {schema_name}: {violations}"
    )
