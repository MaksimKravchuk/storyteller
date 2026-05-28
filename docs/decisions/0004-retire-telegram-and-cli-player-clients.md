# ADR-0004: Retire Telegram and CLI player clients

Date: 2026-05-28
Status: Accepted
Decision owner: Max
Related: `interfaces/`, `main.py`, `run_server.py`, `db/tables.py`, `alembic/versions/a1b2c3d4e5f7_drop_telegram_session_identity.py`

## Context

Storyteller had three player-facing entry points: the web UI, a Telegram bot, and an interactive terminal CLI. The extra clients increased runtime wiring, optional dependencies, test surface, session identity branches, and documentation drift while current beta work targets the browser experience.

Max asked to simplify the codebase by removing the Telegram and CLI clients, including their environment variables and tests.

## Decision

The web UI is the only supported player-facing client. The admin dashboard remains the supported operator interface. Telegram bot code, the interactive CLI entry point, their tests, dependencies, environment variables, and Telegram-specific session identity are removed.

## Rationale

The browser client is the product surface for Friends Beta and future player onboarding. Keeping unsupported clients alive makes every persistence, formatting, logging, QA, and release change pay a multi-client tax without improving the beta path.

Retiring Telegram and CLI removes dead runtime paths and makes session identity web-first instead of carrying an unused `telegram_chat_id` branch through repository and admin code.

## Alternatives considered

### Keep dormant Telegram and CLI code

This would preserve possible future surfaces, but it leaves unused code, optional dependencies, env vars, and tests in place. It was rejected because the current goal is codebase simplification, not dormant compatibility.

### Remove runtime code but keep database fields

This would avoid a migration, but it would preserve Telegram-specific identity in every future persistence and admin schema review. It was rejected because Max asked to clean env vars and tests too, and the simplification should include persisted schema shape.

### Keep CLI as a developer smoke tool

This would offer a quick manual engine harness, but the web UI and direct engine tests cover the supported seams. It was rejected because maintaining a second player client is still maintenance overhead.

## Consequences

Positive consequences:
- Fewer runtime dependencies and startup branches.
- One player-facing session identity model.
- Smaller test suite focused on supported surfaces.
- Less environment-secret and release documentation surface.

Tradeoffs / risks:
- No terminal-only or Telegram manual play path remains.
- Historical databases need the drop migration to remove `sessions.telegram_chat_id`.
- Any future non-web client must be introduced deliberately with fresh rationale and tests.

What future agents must preserve:
- Do not reintroduce Telegram or interactive CLI player clients as incidental debug tools.
- New player surfaces need an explicit product decision and consumer-side tests.
- Keep environment examples and deployment docs aligned with supported runtime clients only.

## Verification / tests

Implementation is preserved by:
- Grepping for Telegram runtime/env references outside historical migrations.
- Running unit tests after deleting Telegram/CLI tests and updating web/admin persistence expectations.
- Running Alembic migration checks where available for `a1b2c3d4e5f7_drop_telegram_session_identity.py`.

## Related files

- `run_server.py`
- `config.py`
- `db/tables.py`
- `db/repo_sessions.py`
- `interfaces/web/`
- `interfaces/admin_dashboard.html`
- `alembic/versions/a1b2c3d4e5f7_drop_telegram_session_identity.py`
- `docs/studio/09-founder-decision-register.md`
