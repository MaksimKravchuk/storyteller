"""Conformance tests for colocated OKF metadata in AGENTS.md files."""

from __future__ import annotations

import re
from importlib import import_module
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urlparse

import allure

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OKF_AGENT_ROOTS = (
    "benchmarks",
    "cast",
    "costs",
    "db",
    "defaults",
    "engine",
    "formatting",
    "interfaces",
    "knowledge",
    "llm",
    "models",
    "prompts",
    "research",
    "safety",
    "tests",
    "timeline",
)
_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


@allure.epic("Documentation")
@allure.feature("Open Knowledge Format")
@allure.story("Scoped AGENTS conformance")
class TestStorytellerOkfAgents:
    @allure.title("Every colocated AGENTS file has parseable OKF frontmatter with type")
    def test_colocated_agents_have_required_okf_type(self) -> None:
        agent_paths = _okf_agent_paths()

        assert agent_paths, "No colocated AGENTS.md files found"

        for agent_path in agent_paths:
            frontmatter, body = _read_concept(agent_path)

            assert isinstance(frontmatter, dict), _message(agent_path, "frontmatter is not a mapping")
            assert frontmatter.get("type"), _message(agent_path, "missing required type field")
            assert body.strip(), _message(agent_path, "body is empty")

    @allure.title("Every colocated AGENTS file explicitly preserves root authority")
    def test_colocated_agents_preserve_root_authority(self) -> None:
        for agent_path in _okf_agent_paths():
            body = _read_concept(agent_path)[1]

            assert "Root `AGENTS.md`" in body, _message(agent_path, "does not preserve root AGENTS.md authority")
            assert "`CLAUDE.md`" in body, _message(agent_path, "does not preserve CLAUDE.md authority")

    @allure.title("Internal markdown links in colocated AGENTS files resolve inside the repo")
    def test_internal_links_resolve_inside_repo(self) -> None:
        for source_path in _okf_agent_paths():
            for link_target in _internal_markdown_links(source_path):
                resolved_target = _resolve_link(source_path, link_target)

                assert resolved_target.exists(), _message(source_path, "broken link to {0}".format(link_target))


def _okf_agent_paths() -> list[Path]:
    agent_paths: set[Path] = set()
    for root_name in _OKF_AGENT_ROOTS:
        agent_paths.update((_REPO_ROOT / root_name).rglob("AGENTS.md"))
    return sorted(agent_paths)


def _read_concept(concept_path: Path) -> tuple[dict[str, object], str]:
    text = concept_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    assert lines and lines[0] == "---", _message(concept_path, "missing opening frontmatter delimiter")

    try:
        closing_index = lines.index("---", 1)
    except ValueError as exc:
        raise AssertionError(_message(concept_path, "missing closing frontmatter delimiter")) from exc

    frontmatter = _load_yaml("\n".join(lines[1:closing_index]))
    body = "\n".join(lines[closing_index + 1 :])
    return frontmatter, body


def _internal_markdown_links(source_path: Path) -> list[str]:
    text = source_path.read_text(encoding="utf-8")
    internal_links: list[str] = []
    for raw_target in _LINK_RE.findall(text):
        clean_target = _strip_link_target(raw_target)
        if not clean_target or _is_external_link(clean_target):
            continue
        if clean_target.endswith(".md") or clean_target.startswith("/"):
            internal_links.append(clean_target)
    return internal_links


def _strip_link_target(raw_target: str) -> str:
    without_fragment = urldefrag(raw_target.strip())[0]
    return without_fragment.split("?", 1)[0]


def _is_external_link(target: str) -> bool:
    parsed = urlparse(target)
    return bool(parsed.scheme or parsed.netloc)


def _resolve_link(source_path: Path, link_target: str) -> Path:
    if link_target.startswith("/"):
        return (_REPO_ROOT / link_target.lstrip("/")).resolve()
    return (source_path.parent / link_target).resolve()


def _message(path: Path, detail: str) -> str:
    return "{0}: {1}".format(path.relative_to(_REPO_ROOT), detail)


def _load_yaml(raw_yaml: str) -> Any:
    yaml_module = import_module("yaml")
    return yaml_module.safe_load(raw_yaml)
