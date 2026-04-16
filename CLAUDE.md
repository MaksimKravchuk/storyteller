# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Storyteller is an AI-powered text quest engine using a theater-style multi-agent architecture. A Director agent coordinates a cast of performer agents (DataMiner, SceneBuilder, NPCGenerator, Narrator, MemoryManager) to research settings via Wikipedia, populate a knowledge graph, and run interactive narratives.

## Commands

```bash
# Install (use uv)
uv sync --group dev --extra openai --extra anthropic

# Run locally
uv run python main.py

# Run the player web UI (FastAPI + vanilla HTML)
uv run uvicorn interfaces.web.app:app --reload --host 127.0.0.1 --port 8070

# Run the full stack with Docker Compose (postgres + storyteller)
# The `storyteller` container runs run_server.py, which boots
# uvicorn (web UI), aiohttp (admin), and the telegram bot in one process.
docker compose up -d            # postgres + storyteller (web + admin + bot)
# Web UI:    http://localhost:8070
# Admin:     http://localhost:8080
# Stop:      docker compose down

# Lint
uv run ruff check .
uv run ruff format --check .
uv run flake8 .

# Type check
uv run mypy .

# Unit tests (excludes e2e + benchmarks)
uv run pytest tests/ --ignore=tests/e2e --ignore=tests/benchmarks -v

# E2E tests (requires OPENAI_API_KEY, ANTHROPIC_API_KEY)
uv run pytest tests/e2e/ --alluredir=allure-results -v

# Benchmarks (opt-in, requires API keys; hits paid LLMs)
uv run python -m benchmarks run
uv run python -m benchmarks run --scenario memory_follow_up_marcus --iterations 1
uv run python -m benchmarks compare <baseline.json> <current.json>
uv run pytest tests/benchmarks -m benchmark -v

# Run single test
uv run pytest tests/test_cli.py -v
uv run pytest tests/test_cli.py::test_function_name -v
```

## Architecture

### Theater Model

All agents inherit from `BasePerformer` (`cast/base_performer_class.py`) which provides LLM abstraction, call-chain tracking, and `_send()`/`_send_json()` methods. The **Director** (`cast/director.py`) is the central orchestrator — it classifies player actions (EXPLORE, MOVE, TALK, etc.), advances the game clock via EventManager, then delegates to specialized agents.

### Turn Flow

Player action → Director routes it → EventManager advances time → SceneBuilder/Actor/NPCGenerator produce content → Narrator converts to prose → GameState updated → response returned.

### Key Modules

- **`cast/`** — All AI agents (director, actor, narrator, scene_builder, npc_generator, data_miner, dice)
- **`engine/`** — Public API (`GameEngine`) and factory; wires agents together
- **`models/`** — Domain models (GameState, Setting, NPCCard, Scene, Location); all inherit UUID-based `BaseModel`
- **`knowledge/`** — NetworkX-backed directed graph with scoped nodes (WORLD→COUNTRY→REGION→CITY→LOCAL), edge types (RELATED_TO, CAUSED_BY, etc.), and scope-filtered querying per NPC education level
- **`timeline/`** — EventManager (game clock, scheduled events with effects) and time cost mapping
- **`llm/`** — Provider-agnostic LLM layer; OpenAI and Anthropic clients with factory auto-detection from model name (`gpt-*`→OpenAI, `claude-*`→Anthropic)
- **`prompts/`** — Composable `PromptTemplate` with `PromptSection`s and variable interpolation; sections with missing vars are skipped
- **`db/`** — Async SQLAlchemy + asyncpg with Alembic migrations; `GameRepository` is the single persistence access point; domain↔ORM conversion in `converters.py`
- **`interfaces/`** — Telegram bot, admin dashboard, and FastAPI web UI (`interfaces/web/`)
- **`research/`** — Async Wikipedia client
- **`benchmarks/`** — Deterministic narration benchmark harness (opt-in, hits paid LLMs). Fixed scenarios drive the engine through `create_engine_from_state()`; captured `TurnOutputs` + `GameState` snapshots are scored against an ISU-style rubric with a six-model witness panel for evidence-LLM elements. Results archive to `benchmarks/results/` as JSON + markdown for release-over-release comparison. Entry point: `uv run python -m benchmarks run`.

### Configuration

`config.py` loads from env vars / `.env` file. Key vars: `DIRECTOR_MODEL` (default gpt-5.4-mini), `AGENT_MODEL` (default gpt-5.4-nano), `NARRATOR_MODEL` (default gpt-5.4-mini), `DEFAULT_PROVIDER` (default openai).

## Code Conventions

- Python 3.11+, async-first throughout
- Line length: 120 (ruff and flake8)
- Full type hints; mypy with `ignore_missing_imports = true`
- Linting: ruff + flake8 with wemake-python-styleguide (many WPS rules suppressed in setup.cfg)
- All agents use the `BasePerformer` pattern: `__init__` takes `llm_client` + system prompt template, `act()` is the async entry point
- Domain models are separate from ORM; `db/converters.py` bridges them
- Tests use pytest-asyncio; fixtures in `tests/conftest.py`

## Git Workflow

- NEVER push directly to `main`. For every code change, create a feature branch (`feat/<topic>` or `fix/<topic>`), commit there, and open a PR with `gh pr create`. The only exception is when I explicitly say "push to main".
- Before every commit, run the full gauntlet and only commit if everything passes:
  ```bash
  uv run ruff check . && uv run ruff format --check . && uv run flake8 . && uv run mypy . && uv run pytest tests/ --ignore=tests/e2e --ignore=tests/benchmarks
  ```
- If lint or type checks fail, REFACTOR the code — do not commit with failures and do not bypass hooks with `--no-verify`.

## Linting Rules

- NEVER suppress WPS / flake8 / mypy violations by:
  - raising limits in `setup.cfg`
  - adding entries to `per-file-ignores`
  - inserting `# noqa`, `# type: ignore`, or `# pragma: no cover` comments
- Always refactor properly: extract helper functions, split modules, use package re-exports, introduce dataclasses, etc. The `fix-wps` skill in `.claude/skills/fix-wps/` has the playbook.
- If a rule genuinely feels wrong for the codebase, present 2–3 refactor options and ask before modifying project config. Suppressions require explicit approval.

## Testing

- For bug fixes, write a failing regression test first (TDD), then fix the root cause. Don't patch around symptoms.
- Maintain 90%+ unit test coverage. When adding new modules, add tests in the same PR.
- E2E tests under `tests/e2e/` must carry Allure annotations following the project taxonomy.
