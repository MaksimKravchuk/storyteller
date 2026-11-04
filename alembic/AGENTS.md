---
type: Component
title: Alembic Migrations
description: Hand-written Alembic revisions that evolve the Postgres schema defined in db/tables.py.
resource: alembic/
tags: [alembic, migrations, postgres, schema]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `alembic/` and `alembic/versions/`.

# Boundary

`alembic/` owns schema migrations only. The current schema shape lives in
`db/tables.py` (SQLAlchemy Core); every column, constraint or index change
there needs a matching revision here, and vice versa. Data access, converters
and repository logic stay in [db](/db/AGENTS.md).

# Contents

- `env.py` — async (asyncpg) runner; targets `db.tables.metadata` and takes
  `DATABASE_URL` through `db.engine._adapt_url_for_asyncpg` so SSL
  `connect_args` apply to migrations too.
- `script.py.mako` — template for `alembic revision`.
- `versions/` — one linear chain, a single head. Files are named
  `<revision>_<snake_case_summary>.py`, e.g.
  `versions/b7c8d9e0f1a2_add_mature_content_to_accounts.py`.
- `README` — the stock Alembic stub.

# Local Rules

- Change `db/tables.py` and add the revision in the same PR (e.g. commit
  b85c8d1 added `accounts.mature_content` to both).
- Set `down_revision` to the current head; keep exactly one head.
- Every revision gets a working `downgrade()`.
- Migrations run on every boot (`run_server._run_migrations` calls
  `alembic upgrade head`), so a broken revision crashloops production.
- Verify with `alembic upgrade head` on a scratch DB (root Demo Contract);
  `tests/db/conftest.py` also upgrades a testcontainer to head.

# Patterns

- Docstring first line says what changes; add the why when it is not obvious,
  e.g. `versions/5c3d9d120dd6_widen_llm_free_text_columns.py`.
- Adding a NOT NULL column to an existing table: give it a `server_default`
  matching `db/tables.py` (`server_default="false"` in
  `versions/b7c8d9e0f1a2_add_mature_content_to_accounts.py`).
- Repeated column ops: drive them from a module-level tuple and loop, as in
  `versions/5c3d9d120dd6_widen_llm_free_text_columns.py`.
- Lossy downgrades truncate explicitly with `postgresql_using`, as in the
  same file, rather than failing on long values.
- CHECK constraints are created with `op.create_check_constraint` and mirror
  the `CheckConstraint` in `db/tables.py`
  (`versions/e8f9a0b1c2d3_restrict_account_plan_values.py`).
- Raw SQL that must be unit-tested lives in a module constant, e.g.
  `UPDATE_NPC_RELATIONSHIPS_SQL` in
  `versions/e1f2a3b4c5d6_promote_relationships_to_typed_model.py`.

# Anti-patterns

- Do not write `:param::jsonb` inside `sa.text()`; the bind regex mangles the
  name and boot crashlooped on Fly. Use `CAST(:param AS jsonb)`. Guarded by
  `tests/test_migration_relationships_jsonb.py`.
- Do not drop the `connect_args` from `_adapt_url_for_asyncpg` in `env.py`;
  guarded by `tests/test_db_engine.py`.
- Do not use bounded `String(n)` for LLM-written text; unbounded output made
  `save_game_state` fail with "value too long" (commit 93d3c6c).
- Do not edit a revision that has already shipped; `upgrade head` skips
  applied revisions, so the edit never reaches existing databases.

# Related

- [DB](/db/AGENTS.md)
- [DB converters](/db/converters/AGENTS.md)
- [DB tests](/tests/db/AGENTS.md)
