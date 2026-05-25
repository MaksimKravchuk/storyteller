"""Dependency matrix: which performer real-LLM tests to run for a given diff.

A diff-driven CI selector reads ``git diff --name-only $BASE...HEAD`` and
asks :func:`select_agents` which agent test files to run. Cross-cutting
files (``llm/``, ``engine/factory.py``, the base performer class, etc.)
trigger every agent. Per-agent code paths (``cast/<agent>*.py``, the
matching prompts and schemas) trigger only that agent. Files that match
no rule (docs, db migrations, deployment configs) contribute nothing —
when the resulting set is empty the e2e step is skipped entirely.

The data structure is intentionally a Python list of ``(glob, frozenset)``
tuples rather than YAML: it's importable, type-checkable, and the seven
keys × ~40 globs do not justify an extra format.

Rule evaluation is **first-match-wins per path**, so put cross-cutting
rules at the top — a touched ``llm/factory.py`` should always trigger
``ALL_AGENTS`` even if a later glob would have matched it.
"""

from __future__ import annotations

from fnmatch import fnmatch
from types import MappingProxyType
from typing import Iterable, Mapping

# A single (glob, agent-set) rule in the matrix.
Rule = tuple[str, frozenset[str]]

AGENT_TO_TEST_FILE: Mapping[str, str] = MappingProxyType(
    {
        "director": "tests/e2e/test_director_agentic_delegation.py",
        "narrator": "tests/e2e/test_narrator_real.py",
        "scene_builder": "tests/e2e/test_scene_builder_real.py",
        "npc_generator": "tests/e2e/test_npc_generator_real.py",
        "data_miner": "tests/e2e/test_data_miner_real.py",
        "actor": "tests/e2e/test_actor_real.py",
        "dramaturge": "tests/e2e/test_dramaturge_real.py",
        "world_chronicler": "tests/e2e/test_world_chronicler_real.py",
    },
)

ALL_AGENTS: frozenset[str] = frozenset(AGENT_TO_TEST_FILE.keys())

# ``fnmatch`` treats ``*`` as "any characters including ``/``" (unlike
# POSIX shell glob), so ``llm/*`` already matches ``llm/sub/file.py``.
# That is why no rule below uses ``**``.
#
# Per-agent singletons are named constants so the rules table reads as
# data, not inline ``frozenset`` literals.
_DIRECTOR: frozenset[str] = frozenset(("director",))
_NARRATOR: frozenset[str] = frozenset(("narrator",))
_SCENE_BUILDER: frozenset[str] = frozenset(("scene_builder",))
_NPC_GENERATOR: frozenset[str] = frozenset(("npc_generator",))
_DATA_MINER: frozenset[str] = frozenset(("data_miner",))
_ACTOR: frozenset[str] = frozenset(("actor",))
_DRAMATURGE: frozenset[str] = frozenset(("dramaturge",))
_WORLD_CHRONICLER: frozenset[str] = frozenset(("world_chronicler",))
_NARRATOR_AND_CHRONICLER: frozenset[str] = frozenset(("narrator", "world_chronicler"))
_ACTOR_AND_DIRECTOR: frozenset[str] = frozenset(("actor", "director"))

PATH_TRIGGERS: tuple[Rule, ...] = (
    # ── Cross-cutting: any change here invalidates every agent ──
    ("cast/base_performer_class.py", ALL_AGENTS),
    ("cast/_performer_retry.py", ALL_AGENTS),
    ("cast/constants.py", ALL_AGENTS),
    ("llm/*", ALL_AGENTS),
    ("engine/factory.py", ALL_AGENTS),
    ("engine/engine_wiring.py", ALL_AGENTS),
    ("engine/model_overrides.py", ALL_AGENTS),
    ("config.py", ALL_AGENTS),
    ("defaults/models.py", ALL_AGENTS),
    ("prompts/base_template.py", ALL_AGENTS),
    ("prompts/locales.py", ALL_AGENTS),
    ("pyproject.toml", ALL_AGENTS),
    ("tests/e2e/_real_llm.py", ALL_AGENTS),
    ("tests/e2e/_agent_matrix.py", ALL_AGENTS),
    ("tests/e2e/_select_agents.py", ALL_AGENTS),
    (".github/workflows/ci.yml", ALL_AGENTS),
    ("tests/conftest.py", ALL_AGENTS),
    ("tests/base_performer_helpers.py", ALL_AGENTS),
    # ── Director ──
    ("cast/director*.py", _DIRECTOR),
    ("cast/schemas/action_plan*.py", _DIRECTOR),
    ("cast/schemas/_action_plan*.py", _DIRECTOR),
    ("cast/schemas/plan_access.py", _DIRECTOR),
    ("prompts/director_prompts*.py", _DIRECTOR),
    ("tests/director_helpers.py", _DIRECTOR),
    ("tests/e2e/test_director_agentic_delegation.py", _DIRECTOR),
    # ── Narrator (shares turn_outputs schema with WorldChronicler) ──
    ("cast/narrator*.py", _NARRATOR),
    ("cast/visible_entities.py", _NARRATOR),
    ("cast/player_context.py", _NARRATOR),
    ("cast/wait_detection.py", _NARRATOR),
    ("cast/schemas/turn_outputs.py", _NARRATOR_AND_CHRONICLER),
    ("prompts/narrator_prompts*.py", _NARRATOR),
    ("tests/e2e/test_narrator_real.py", _NARRATOR),
    # ── SceneBuilder ──
    ("cast/scene_builder.py", _SCENE_BUILDER),
    ("cast/_scene_location.py", _SCENE_BUILDER),
    ("cast/scene_log*.py", _SCENE_BUILDER),
    ("cast/scene_swap.py", _SCENE_BUILDER),
    ("cast/schemas/scene_response.py", _SCENE_BUILDER),
    ("prompts/scene_builder_prompts*.py", _SCENE_BUILDER),
    ("tests/e2e/test_scene_builder_real.py", _SCENE_BUILDER),
    # ── NPCGenerator ──
    ("cast/npc_generator.py", _NPC_GENERATOR),
    ("cast/_npc_generator_goals.py", _NPC_GENERATOR),
    ("cast/known_npcs.py", _NPC_GENERATOR),
    ("cast/schemas/npc_response.py", _NPC_GENERATOR),
    ("prompts/npc_generator_prompts*.py", _NPC_GENERATOR),
    ("tests/e2e/test_npc_generator_real.py", _NPC_GENERATOR),
    # ── DataMiner ──
    ("cast/data_miner.py", _DATA_MINER),
    ("cast/_data_miner_init.py", _DATA_MINER),
    ("research/*", _DATA_MINER),
    ("cast/schemas/setting_response.py", _DATA_MINER),
    ("prompts/data_miner_prompts*.py", _DATA_MINER),
    ("tests/e2e/test_data_miner_real.py", _DATA_MINER),
    # ── Actor (hostility is shared with Director routing) ──
    ("cast/actor.py", _ACTOR),
    ("cast/actor_config.py", _ACTOR),
    ("cast/hostility.py", _ACTOR_AND_DIRECTOR),
    ("cast/_npc_active_goal.py", _ACTOR),
    ("cast/_npc_combat_memory.py", _ACTOR),
    ("cast/_npc_outcome.py", _ACTOR),
    ("cast/_npc_tactical_goal.py", _ACTOR),
    ("cast/_npc_aftermath_chain.py", _ACTOR),
    ("cast/npc_turn.py", _ACTOR),
    ("cast/npc_ticker.py", _ACTOR),
    ("cast/npc_background_tick.py", _ACTOR),
    ("cast/npc_goal_resolution.py", _ACTOR),
    ("cast/npc_opportunity.py", _ACTOR),
    ("cast/schemas/actor_reply.py", _ACTOR),
    ("knowledge/query.py", _ACTOR),
    ("prompts/actor_prompts*.py", _ACTOR),
    ("tests/actor_helpers.py", _ACTOR_AND_DIRECTOR),
    ("tests/e2e/test_actor_real.py", _ACTOR),
    # ── Dramaturge ──
    ("cast/dramaturge.py", _DRAMATURGE),
    ("cast/schemas/dramaturge_response.py", _DRAMATURGE),
    ("prompts/dramaturge_prompts*.py", _DRAMATURGE),
    ("tests/e2e/test_dramaturge_real.py", _DRAMATURGE),
    # ── WorldChronicler ──
    ("cast/world_chronicler.py", _WORLD_CHRONICLER),
    ("cast/_chronicler_goals.py", _WORLD_CHRONICLER),
    ("cast/schemas/chronicler_response.py", _WORLD_CHRONICLER),
    ("prompts/chronicler_prompts*.py", _WORLD_CHRONICLER),
    ("tests/e2e/test_world_chronicler_real.py", _WORLD_CHRONICLER),
)


def select_agents(changed_paths: Iterable[str]) -> set[str]:
    """Map changed file paths to the set of agent keys whose tests to run.

    Glob-based, first-match-wins per path. An empty result means no
    e2e tests need to run for this diff.
    """
    selected: set[str] = set()
    for path in changed_paths:
        for glob, agents in PATH_TRIGGERS:
            if fnmatch(path, glob):
                selected |= agents
                break
    return selected


def selected_test_files(agents: Iterable[str]) -> list[str]:
    """Return the sorted list of e2e test file paths for these agent keys."""
    known = (agent for agent in agents if agent in AGENT_TO_TEST_FILE)
    return sorted({AGENT_TO_TEST_FILE[agent] for agent in known})
