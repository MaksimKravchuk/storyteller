---
type: Component
title: Cast
description: Performer agents and turn orchestration code for Storyteller's theater runtime.
resource: cast/
tags: [cast, agents, runtime]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `cast/`.

# Boundary

`cast/` owns the Director and performer agents. Performer agents use the
`BasePerformer` pattern for LLM calls, structured JSON, context passing, and
call-chain logging.

# Local Rules

- Treat prompt-variable wiring and agent response schemas as consumer contracts.
- Prefer consumer-side tests that prove downstream prompts or runtime code
  receive the new value.
- Coordinate schema changes with [cast schemas](/cast/schemas/AGENTS.md) and
  prompt changes with [prompts](/prompts/AGENTS.md).
- Narrative-affecting behavior may require approved benchmark evidence.

# Related

- [Engine](/engine/AGENTS.md)
- [Knowledge](/knowledge/AGENTS.md)
- [Models](/models/AGENTS.md)

