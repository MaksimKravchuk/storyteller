---
type: Component
title: Defaults
description: Default model selections and default player-character data.
resource: defaults/
tags: [defaults, configuration, models]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `defaults/`.

# Boundary

`defaults/` owns code-level defaults for model selection, player-character
setup, and user-plan entitlements. Env parsing stays in `config.py`; wire
behavior per model stays in [llm](/llm/AGENTS.md).

# Contents

- `models.py` — provider constants, frozen `ModelConfig`, and the `AI_MODELS`
  registry shared by the engine, benchmarks and judges.
- `player_character.py` — `TEMPLATE_CHARACTER` for the web "Use template"
  button and deterministic test fixtures.
- `entitlements.py` — `UserPlan` values, `PlanQuotaSettings`,
  `normalize_user_plan`, `quota_settings_for_plan`.

# Local Rules

- Do not use defaults to hide environment-specific configuration.
- Coordinate player-character defaults with [models](/models/AGENTS.md).
- Coordinate model defaults with [llm](/llm/AGENTS.md).
- Role defaults (`gpt-6-luna`) live in `config.py` and
  `engine/game_engine.py`; change them together
  (`docs/decisions/0018-default-agent-roles-to-gpt-6-luna.md`).

# Patterns

- Add a model as a new `AI_MODELS` attribute built from `ModelConfig`; add its
  price in `costs/model_pricing.py`.
- Quota numbers come from `Config` (`_quota_settings_by_plan`); `None` means
  uncapped.
- Unknown or missing plan values normalize to `DEFAULT_USER_PLAN`, never to
  admin.

# Anti-patterns

- Repointing a shared `AI_MODELS` entry casually: judges and smoke probes
  read it, so it changes the benchmark instrument
  (`docs/decisions/0019-refresh-judge-panel-to-current-models.md`).
- Removing `gpt5_4*` entries; non-judge code and tests still use them
  (ADR-0019).
- Hard-coding quota numbers here instead of reading `Config`
  (`tests/test_beta_web_policy.py`).

# Related

- [LLM](/llm/AGENTS.md)
- [Models](/models/AGENTS.md)
- [Costs](/costs/AGENTS.md)
- [Benchmarks](/benchmarks/AGENTS.md)
