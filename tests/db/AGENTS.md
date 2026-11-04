---
type: Component
title: DB Tests
description: Real-Postgres integration tests for GameRepository and its sub-repositories.
resource: tests/db/
tags: [tests, db, postgres, integration]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `tests/db/`.

# Boundary

`tests/db/` owns tests that need a real Postgres: repository queries, save /
load round trips, and migrations applied by Alembic. Pure converter or mocked
repository tests stay in `tests/` (e.g. `tests/test_db_converters.py`,
`tests/test_repo_settings_mocked.py`).

# Contents

- `conftest.py` — skips the package when `docker info` fails; pops the
  `tests/_db_stubs.py` stubs and loads real `db.engine` / `db.repository`;
  starts `postgres:16` via testcontainers once per session and runs
  `alembic upgrade head`; provides `async_session`, `async_engine`, `repo`,
  `test_session_id`, and the `populated_game_state` builder.
- `test_repository.py`, `test_repo_*.py`, `test_web_session.py` — one file
  per repository area (admin, ai_logs, feedback, posters, settings, ...).
- `test_round_trip.py`, `test_repo_loader.py`, `test_repo_saver.py` —
  save -> load -> mutate -> save -> load of full `GameState`.

# Local Rules

- Mark every module `pytestmark = pytest.mark.db`; the default `addopts`
  deselects `db`, so run with `uv run pytest tests/db -m db` (needs Docker).
- Allure labels are required here, same as unit tests.
- New migrations are exercised automatically by the session fixture; a
  failing `alembic upgrade head` fails every DB test.

# Patterns

- Use the `repo` fixture: a real `GameRepository` on a savepointed session
  whose outer transaction always rolls back, so tests may insert freely.
- Import `GameRepository` from `tests.db.conftest`, as
  `tests/db/test_round_trip.py` does, so you get the real class, not the stub.
- Create a session row with `test_session_id` before saving state.
- Reuse `populated_game_state` for full-state round trips instead of
  hand-building settings, locations and NPCs.

# Anti-patterns

- Sharing an engine across tests: asyncpg connections cannot cross event
  loops, so `conftest.py` builds and disposes one engine per test.
- Trusting `DATABASE_URL`: `_run_alembic_upgrade` drops it during upgrade
  so a developer `.env` cannot redirect migrations to a real database.
- Opening your own engine or session in a test: it bypasses the rollback
  wrapper and leaks rows into later tests.

# Related

- [Tests](/tests/AGENTS.md)
- [DB](/db/AGENTS.md)
- [Alembic](/alembic/AGENTS.md)
