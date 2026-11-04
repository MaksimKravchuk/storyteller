---
type: Component
title: Cast Schemas
description: Structured response models shared by Director planning and performer agent outputs.
resource: cast/schemas/
tags: [cast, schemas, pydantic]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `cast/schemas/`.

# Boundary

`cast/schemas/` defines typed payloads for action plans, performer outputs, and
turn outputs. It holds Pydantic shapes and tiny accessors only; no LLM calls,
no prompt text, and no game-state mutation (that lives in [cast](/cast/AGENTS.md)).

# Contents

- `action_plan.py` — the `ActionPlan` discriminated union on `action_type`
  plus `ClarificationRequest`; verb plans live in `_action_plan_base.py`,
  `_action_plan_verbs_simple.py`, `_action_plan_verbs_targeted.py`.
- `plan_access.py` — `targets`, `is_aggressive`, `delegate_to`, `contest`
  accessors that work across every plan variant.
- Performer responses: `actor_reply.py`, `scene_response.py`,
  `npc_response.py`, `item_response.py`, `setting_response.py`,
  `chronicler_response.py`, `dramaturge_response.py`, `anachronism.py`.
- `turn_outputs.py` — `TurnOutputs` and its entries (`DialogueEntry`,
  `NPCTurnEntry`, `WaitContext`): everything a Director turn hands the Narrator.

# Local Rules

- Treat schema fields as contracts with the consumer that reads them.
- For new fields, add tests at the consumer seam, not only model validation.
- Keep schema names and access helpers aligned with [cast](/cast/AGENTS.md)
  runtime usage.
- A field the LLM fills needs matching prompt text in both EN and RU
  [prompts](/prompts/AGENTS.md) (e.g. `SceneResponse.location_name`, ADR-0023).

# Patterns

- LLM-facing models set `model_config = ConfigDict(extra="forbid")` and give
  each field a `Field(description=...)`, as in `_action_plan_base._PlanBase`.
- Optional output fields get a default (`location_name: str = ""`,
  `Field(default_factory=list)`) so older or sparse replies still validate.
- Read plan attributes through `plan_access` (`plan_access.targets(plan)`)
  instead of `getattr` at each call site.
- Document who populates and who consumes a field in the model docstring,
  as `TurnOutputs` does for `witnessed_events` and `intent`.
- Split a module that hits the flake8 member budget into underscore-private
  modules re-exported by the public one (`_action_plan_verbs_simple.py`).

# Anti-patterns

- `dict[str, Any]` or other free-form object fields: OpenAI strict mode
  needs `additionalProperties: false` on every object. Guarded by
  `tests/test_strict_schema_regression.py`, which scans every model here.
- `UUID4` fields: Pydantic emits `format: uuid4`, which strict mode rejects
  (same test file).
- Relying on schema-only hints: for Anthropic `llm/_anthropic_schema.py`
  strips `maxItems`, integer ranges and `description`, so a capped list is
  only checked after the reply. Put must-follow rules in the prompt
  (`tests/test_anthropic_schema.py`).
- Putting player-facing NPC names into a payload without
  `NPCCard.label_for_player`; leaked unmet names in `npc_departures`
  (`docs/decisions/0007-gate-npc-departure-names-at-ticker-source.md`).

# Related

- [Models](/models/AGENTS.md)
- [Prompts](/prompts/AGENTS.md)
- [LLM](/llm/AGENTS.md)
