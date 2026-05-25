"""Shared helper for the per-agent real-LLM smoke tests.

The tests under ``tests/e2e/test_*_real.py`` (including the existing
``test_director_agentic_delegation.py``) exercise each performer against
the configured live model. Every performer ultimately reads its model id
from one of the four knobs on :class:`config.Config` (``director_model``,
``narrator_model``, ``dramaturge_model``, or the catch-all
``agent_model``). This module centralises the ``config → ModelConfig →
api_key → BaseLLMClient`` plumbing so each test file is a one-liner:
``real_llm_for("narrator")``.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping

import pytest

import config as config_mod
from llm import factory as llm_factory

if TYPE_CHECKING:
    from llm.base_client import BaseLLMClient

# The four agents not in this set share the catch-all ``agent_model`` knob.
_AGENT_MODEL_ATTR = "agent_model"

# Maps an agent key (also used by the dependency matrix and the test-file
# naming convention) to the attribute on :class:`config.Config` that
# names its model. Director/Narrator/Dramaturge have dedicated knobs; the
# remaining four performers share ``agent_model`` because that is how
# :mod:`engine.factory` wires them today.
AGENT_TO_MODEL_ATTR: Mapping[str, str] = MappingProxyType(
    {
        "director": "director_model",
        "narrator": "narrator_model",
        "dramaturge": "dramaturge_model",
        "npc_generator": _AGENT_MODEL_ATTR,
        "scene_builder": _AGENT_MODEL_ATTR,
        "actor": _AGENT_MODEL_ATTR,
        "data_miner": _AGENT_MODEL_ATTR,
        "world_chronicler": _AGENT_MODEL_ATTR,
    },
)


def real_llm_for(agent: str) -> "BaseLLMClient":
    """Create the configured LLM client for ``agent``, or ``pytest.skip`` it.

    The skip message names which environment variable to set so a missing
    key in CI is debuggable in one glance.
    """
    if agent not in AGENT_TO_MODEL_ATTR:
        raise KeyError(f"Unknown agent key: {agent!r}. Known: {sorted(AGENT_TO_MODEL_ATTR)}")
    config = config_mod.load_config()
    model_attr = AGENT_TO_MODEL_ATTR[agent]
    model_id = getattr(config, model_attr)
    model_config = config_mod.resolve_model_config(model_id)
    api_key = config_mod.get_api_key_for_provider(model_config.provider, config)
    if not api_key:
        pytest.skip(
            "No API key for {0} ({1} via {2}={3}); set {4}_API_KEY to run real-LLM smoke test.".format(
                agent,
                model_config.provider,
                model_attr.upper(),
                model_id,
                model_config.provider.upper(),
            ),
        )
    return llm_factory.create_llm_client(model_config, api_key=api_key)
