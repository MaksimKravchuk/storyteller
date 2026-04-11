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
uv run uvicorn interfaces.web.app:app --reload --host 127.0.0.1 --port 8000

# Run the full stack with Docker Compose (postgres + telegram/admin + web UI)
docker compose up -d            # all services
docker compose up -d postgres web  # web UI only (no telegram)
# Web UI:    http://localhost:8000
# Admin:     http://localhost:8080
# Stop:      docker compose down

# Lint
uv run ruff check .
uv run ruff format --check .
uv run flake8 .

# Type check
uv run mypy .

# Unit tests (excludes e2e)
uv run pytest tests/ --ignore=tests/e2e -v

# E2E tests (requires OPENAI_API_KEY, ANTHROPIC_API_KEY)
uv run pytest tests/e2e/ --alluredir=allure-results -v

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

### Configuration

`config.py` loads from env vars / `.env` file. Key vars: `DIRECTOR_MODEL` (default gpt-4), `AGENT_MODEL` (default gpt-3.5-turbo), `NARRATOR_MODEL` (default gpt-4), `DEFAULT_PROVIDER` (default openai).

## Code Conventions

- Python 3.11+, async-first throughout
- Line length: 120 (ruff and flake8)
- Full type hints; mypy with `ignore_missing_imports = true`
- Linting: ruff + flake8 with wemake-python-styleguide (many WPS rules suppressed in setup.cfg)
- All agents use the `BasePerformer` pattern: `__init__` takes `llm_client` + system prompt template, `act()` is the async entry point
- Domain models are separate from ORM; `db/converters.py` bridges them
- Tests use pytest-asyncio; fixtures in `tests/conftest.py`
