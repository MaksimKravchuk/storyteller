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
domain/ORM conversion. It does not own schema migrations
([alembic](/alembic/AGENTS.md)), HTTP handling, or game logic.

# Contents

- `tables.py` — SQLAlchemy Core `Table` definitions (not ORM-mapped);
  `metadata` is the Alembic target.
- `engine.py` — async engine, session factory, `get_db()` commit/rollback
  scope, and `_adapt_url_for_asyncpg` for managed-Postgres URLs.
- `repository.py` — `GameRepository` facade that composes the stores below.
- `repo_saver.py`, `repo_saver_helpers.py` — `StateSaver`: upsert
  `game_states`, then delete+insert child rows.
- `repo_loader.py`, `repo_loader_helpers.py` — `StateLoader`: rows back to
  `GameState`, `KnowledgeGraph`, events.
- `repo_sessions.py`, `repo_web_games.py`, `repo_posters.py` — sessions and
  the web story library.
- `repo_accounts.py`, `repo_beta_invites.py`, `repo_feedback.py` — accounts
  and beta program.
- `repo_ai_logs.py`, `repo_turn_events.py` — AI call logs and per-turn events.
- `repo_settings.py`, `repo_settings_search.py` — admin key/value overrides.
- `repo_admin*.py` — read-only admin dashboard queries.
- `converters/` — domain ↔ row mapping (see its own AGENTS.md).

# Local Rules

- Keep `GameRepository` as the persistence access point.
- Do not merge ORM shape into [models](/models/AGENTS.md).
- Prove persistence changes through repository round-trip tests
  (`tests/db/`, Docker required; mocked-session tests such as
  `tests/test_repo_saver_uuid.py` run anywhere).
- Coordinate model conversion changes with [db converters](/db/converters/AGENTS.md).
- A schema change in `tables.py` ships with an Alembic revision.

# Patterns

- New store: a class taking `AsyncSession` in `__init__`, exposed on
  `GameRepository` (copy `TurnEventStore` in `repo_turn_events.py`).
- Child collections are replaced per save via
  `repo_saver_helpers.replace_rows`; one-to-one rows use
  `upsert_one_to_one` keyed on `game_state_id`.
- A new `game_states` column goes in both `.values()` and the
  `on_conflict_do_update` `set_` in `StateSaver.save`.
- Loaders tolerate stale rows: `repo_loader_helpers` drops a bad scene-log
  entry loudly instead of failing the whole load.
- Per-turn metrics ride `turn_events.payload` via `record_turn_event`, not a
  new table or column (ADR-0002).

# Anti-patterns

- Do not assume `game_state.uuid` is the stored id: the upsert on
  `session_id` keeps the old row id, and `StateSaver.save` copies it back.
  Guarded by `tests/test_repo_saver_uuid.py`.
- Do not drop knowledge-edge metadata or actor-root edges on save/load
  (ADR-0008; `tests/db/test_repo_loader.py`).
- Do not discard `connect_args` from `_adapt_url_for_asyncpg`; SSL settings
  would be lost (`tests/test_db_engine.py`).
- Do not remove `pool_pre_ping` / `pool_recycle` from `create_async_engine`;
  stale pooled connections caused the beta-auth 500s (comment in
  `engine.py`).

# Related

- [Engine](/engine/AGENTS.md)
- [Knowledge](/knowledge/AGENTS.md)
- [Alembic](/alembic/AGENTS.md)
- [DB tests](/tests/db/AGENTS.md)
