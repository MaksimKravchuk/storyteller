---
type: Component
title: DB Converters
description: Domain-to-ORM conversion helpers for persisted Storyteller state.
resource: db/converters/
tags: [db, converters, persistence]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `db/converters/`.

# Boundary

`db/converters/` translates between domain models and database rows.

# Local Rules

- Treat converter edits as persistence-contract changes.
- Add tests that prove values survive save/load through [db](/db/AGENTS.md).
- Preserve knowledge graph edge metadata and actor-root edges.
- This directory is in the mutation-testing scope.

# Related

- [Models](/models/AGENTS.md)
- [Knowledge](/knowledge/AGENTS.md)

