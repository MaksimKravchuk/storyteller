---
type: Component
title: Engine
description: Public GameEngine API and wiring layer that connects models, cast agents, timeline, knowledge, and persistence.
resource: engine/
tags: [engine, runtime, wiring]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `engine/`.

# Boundary

`engine/` owns the public `GameEngine` API, factory/wiring code, turn lifecycle,
session restoration, and persistence handoff.

# Local Rules

- Keep orchestration in the engine and agent behavior in [cast](/cast/AGENTS.md).
- Preserve persistence boundaries with [db](/db/AGENTS.md).
- Changes to turn flow, player-facing behavior, or narrative paths need
  consumer-side tests and may need benchmark evidence.

# Related

- [Knowledge](/knowledge/AGENTS.md)
- [Timeline](/timeline/AGENTS.md)
- [Interfaces](/interfaces/AGENTS.md)

