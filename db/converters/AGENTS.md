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

`db/converters/` translates between domain models and database rows. It holds
pure functions only: no session, no SQL, no I/O. Saving and loading belong to
[db](/db/AGENTS.md).

# Contents

- One module per domain type, each with a `<type>_to_row` / `row_to_<type>`
  pair: `event.py`, `knowledge.py` (nodes and edges), `location.py`,
  `npc.py`, `player.py`, `scene.py`, `setting.py`, `world_state.py`.
- `_columns.py` — shared column-name constants (`COL_ID`, `COL_SCOPE`, ...).
- `_uuid_text.py` — `uuid_to_text` for UUID fields bound to `Text` columns.
- `_npc_relationships.py` — typed relationship list ↔ JSONB, including the
  legacy dict upcast.

# Local Rules

- Treat converter edits as persistence-contract changes.
- Add tests that prove values survive save/load through [db](/db/AGENTS.md).
- Preserve knowledge graph edge metadata and actor-root edges.
- This directory is in the mutation-testing scope (ADR-0005).
- A new model field needs both directions here, the column in
  `db/tables.py`, and an [Alembic](/alembic/AGENTS.md) revision.

# Patterns

- Round-trip test every new field in `tests/test_db_converters.py`
  (domain → row → domain, no DB needed).
- Read newer columns with a default so older rows still load:
  `row.get(_COL_SALIENCE, salience_presets.DEFAULT)` in
  `knowledge.row_to_knowledge_node`, `row.get("values_vector") or {}` in
  `npc.row_to_npc`.
- Nested Pydantic values go out as `model_dump(mode="json")` and come back via
  `model_validate` (`_goal_to_row` / `_row_to_goal` in `npc.py`).
- Edge metadata is made JSONB-safe recursively by
  `knowledge.edge_metadata_to_json` (UUID → str, Enum → value).
- Legacy payload shapes are upcast on read, not migrated in place
  (`row_to_relationships` in `_npc_relationships.py`).

# Anti-patterns

- Do not bind raw `uuid.UUID` to `Text` columns (`location_id`, `owner_id`,
  `subject_id`); asyncpg rejects them. Wrap with `uuid_to_text`.
- Do not filter edge metadata on save; ADR-0008 tests in
  `tests/db/test_repo_loader.py` check told-by and actor-root edges survive
  reload.
- Do not add string literals for shared column names; WPS flags repeated
  literals, which is why `_columns.py` exists.

# Related

- [Models](/models/AGENTS.md)
- [Knowledge](/knowledge/AGENTS.md)
- [Alembic](/alembic/AGENTS.md)
