---
type: Component
title: DB
description: Async SQLAlchemy persistence layer for sessions, game state, knowledge graph data, turn events, and admin reads.
resource: db/
tags: [db, persistence, sqlalchemy]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `db/`.

# Boundary

`db/` owns persistence tables, repository save/load flows, admin reads, and
domain/ORM conversion.

# Local Rules

- Keep `GameRepository` as the persistence access point.
- Do not merge ORM shape into [models](/models/AGENTS.md).
- Prove persistence changes through repository round-trip tests.
- Coordinate model conversion changes with [db converters](/db/converters/AGENTS.md).

# Related

- [Engine](/engine/AGENTS.md)
- [Knowledge](/knowledge/AGENTS.md)

