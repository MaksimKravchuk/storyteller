---
type: Component
title: Knowledge
description: NetworkX-backed world knowledge, rumors, hearsay, personal memories, and scoped query behavior.
resource: knowledge/
tags: [knowledge, graph, memory]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `knowledge/`.

# Boundary

`knowledge/` owns world facts, rumors, hearsay, scene summaries, and NPC-held
personal memories.

# Local Rules

- Preserve actor-root `WITNESSED` edges for personal memory.
- Preserve `TOLD_BY` edge metadata for recipient-owned hearsay.
- Keep graph serialization compatible with [db](/db/AGENTS.md) round trips.
- This directory is in the mutation-testing scope; follow the root mutation
  guidance for release-sensitive changes.

# Related

- [Cast](/cast/AGENTS.md)
- [Models](/models/AGENTS.md)
- [DB converters](/db/converters/AGENTS.md)

