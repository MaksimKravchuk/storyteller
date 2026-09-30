# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Storyteller is an AI-powered text quest engine using a theater-style multi-agent architecture. A Director agent coordinates a cast of performer agents (DataMiner, SceneBuilder, NPCGenerator, Narrator, MemoryManager) to research settings via Wikipedia, populate a knowledge graph, and run interactive narratives.

## Commands

```bash
# Install (use uv)
uv sync --group dev --extra openai --extra anthropic

# Run the player web UI (FastAPI + vanilla HTML)
uv run uvicorn interfaces.web.app:app --reload --host 127.0.0.1 --port 8070

# Run the full stack with Docker Compose (postgres + storyteller)
# The `storyteller` container runs run_server.py, which boots
# uvicorn (web UI) and aiohttp (admin) in one process.
docker compose up -d            # postgres + storyteller (web + admin)
# Web UI:    http://localhost:8070
# Admin:     http://localhost:8080
# Stop:      docker compose down

# Lint / type-check (run individually while iterating)
uv run ruff check .
uv run ruff format --check .
uv run flake8 .
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
uv run pytest tests/test_web_api.py -v
uv run pytest tests/test_web_api.py::test_function_name -v
```

## Architecture

### Theater Model

All agents inherit from `BasePerformer` (`cast/base_performer_class.py`) which provides LLM abstraction, call-chain tracking, and `_send()`/`_send_json()` methods. The **Director** (`cast/director.py`) is the central orchestrator — it classifies player actions (EXPLORE, MOVE, TALK, etc.), advances the game clock via EventManager, then delegates to specialized agents.

### Turn Flow

Player action → Director routes it → EventManager advances time → SceneBuilder/Actor/NPCGenerator produce content → Narrator converts to prose → GameState updated → response returned.

### Key Modules

- **`cast/`** — All AI agents (director, actor, narrator, scene_builder, npc_generator, data_miner, dramaturge, world_chronicler, dice)
- **`engine/`** — Public API (`GameEngine`) and factory; wires agents together
- **`models/`** — Domain models (GameState, Setting, NPCCard, Scene, Location); all inherit UUID-based `BaseModel`
- **`knowledge/`** — NetworkX-backed directed graph with scoped nodes (WORLD→COUNTRY→REGION→CITY→LOCAL), edge types (RELATED_TO, CAUSED_BY, etc.), and scope-filtered querying per NPC education level
- **`timeline/`** — EventManager (game clock, scheduled events with effects) and time cost mapping
- **`llm/`** — Provider-agnostic LLM layer; OpenAI, Anthropic, OpenRouter, and DeepSeek clients with factory auto-detection from model name (`gpt-*`→OpenAI, `claude-*`→Anthropic)
- **`prompts/`** — Composable `PromptTemplate` with `PromptSection`s and variable interpolation; sections with missing vars are skipped
- **`db/`** — Async SQLAlchemy + asyncpg with Alembic migrations; `GameRepository` is the single persistence access point; domain↔ORM conversion in `converters.py`
- **`interfaces/`** — Admin dashboard and FastAPI web UI (`interfaces/web/`)
- **`research/`** — Async Wikipedia client
- **`benchmarks/`** — Deterministic narration benchmark harness (opt-in, hits paid LLMs). Fixed scenarios drive the engine through `create_engine_from_state()`; captured `TurnOutputs` + `GameState` snapshots are scored against an ISU-style rubric with a six-model witness panel for evidence-LLM elements. Results archive to `benchmarks/results/` as JSON + markdown for release-over-release comparison. Entry point: `uv run python -m benchmarks run`. Also runs automatically on PRs touching `cast/`, `prompts/`, `engine/`, or `benchmarks/scenarios/` via `.github/workflows/benchmark-on-pr.yml` (1 iteration, 3-judge panel, ~$0.02–$0.10 per push).

### Configuration

`config.py` loads from env vars / `.env`. Per-agent model vars: `DIRECTOR_MODEL` (default gpt-5.4-mini), `AGENT_MODEL` (gpt-5.4-nano), `NARRATOR_MODEL` (gpt-5.4-mini), `DRAMATURGE_MODEL` (gpt-5.4-nano). Provider is auto-detected from each model name (no global provider var). The Dramaturge consistency pass is off by default — enable with `DRAMATURGE_ENABLED=true`.

## Code Conventions

- Python 3.11+, async-first throughout
- Line length: 120 (ruff and flake8)
- Full type hints; mypy with `ignore_missing_imports = true`
- Linting: ruff + flake8 with wemake-python-styleguide (many WPS rules suppressed in setup.cfg)
- All agents use the `BasePerformer` pattern: `__init__` takes `llm_client` + system prompt template, `act()` is the async entry point
- Domain models are separate from ORM; `db/converters.py` bridges them
- Tests use pytest-asyncio; fixtures in `tests/conftest.py`

## Git Workflow

- Trunk development: `main` is the only long-lived development branch. For code changes, create a short-lived branch (`feat/<topic>`, `fix/<topic>`, `docs/<topic>`, or `chore/<topic>`), commit there, push it, and open a PR with `gh pr create` early. PR review is the default code-review surface.
- Agents may create branches, push them, and open PRs for code work without asking first. NEVER push directly to `main` unless Max explicitly says "push to main".
- Agents may merge low-risk PRs after the required deterministic checks and CI pass. Stop and ask before merging product/release behavior changes, destructive data changes, paid/e2e/benchmark-dependent changes, or anything with unclear risk.
- Release tags are the release boundary: cut annotated tags from `main` only after Max approval and the release checklist. See `docs/decisions/0014-trunk-development-with-release-tags.md`.
- For non-trivial feature work, use the Spec Kit requirements layer before implementation when it materially improves clarity: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` for medium work; add `/speckit-clarify` (blocking unknowns only) and one `/speckit-analyze` pass for large/risky work; `/speckit-checklist` and `/speckit-converge` are opt-in. See `docs/decisions/0017-adopt-spec-kit-as-requirements-layer.md`, `docs/studio/13-spec-driven-development.md`, and `.specify/memory/constitution.md`.
- Treat `/speckit-implement` as optional, not the default autopilot. Spec Kit review steps fix only blocking contradictions: one remediation pass, then escalate to Max; never grow scope while fixing findings (constitution Principle VI). Implementation still follows this file, AGENTS.md, accepted ADRs, deterministic verification, and PR review.
- Before changing architecture, agent roles, prompt boundaries, persistence behavior, release strategy, or player-facing behavior, inspect accepted decision records in `docs/decisions/` and `docs/studio/09-founder-decision-register.md`.
- When making a new significant decision in any of those areas, use the `decision-records` skill and create or update a record covering context, decision, rationale, alternatives, consequences, verification, and future-agent guardrails.
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

## Default workflow: stakeholder mode

The user operates as **stakeholder**, not project manager. They state a task with success criteria; the assistant plans, implements, and ships a working demo. **No upstream story / brief / QA-plan approvals.** The surviving gates are: (a) the pre-commit gauntlet from the Git Workflow section, (b) decision-record inspection + invocation per Git Workflow when the change touches the listed boundaries, and (c) PR review/CI visibility before merge. Per ADR-0014, agents may merge low-risk green PRs without waiting for a separate approval.

**Ambiguity rule:** when something load-bearing is genuinely ambiguous mid-task, stop and ask. Cosmetic / reversible choices are decided silently.

### Hermes Kanban workers and Claude Code print mode

When a Hermes Kanban worker is assigned a Storyteller coding, debugging, refactoring, or review card, prefer using Claude Code print mode (`claude -p`) for non-trivial inner-loop work. Hermes should still own task scoping, final diff inspection, verification, and the Kanban complete/block handoff.

Implementation template:

```bash
claude -p "
You are working inside Storyteller.

Task:
<task body>

Rules:
- Follow CLAUDE.md and AGENTS.md.
- Keep changes surgical and minimal.
- For bug fixes, write or adjust the regression test first and observe it fail before fixing.
- You may push a short-lived branch and open a PR when the implementation is verified.
- Do not run paid/e2e/benchmark checks unless Max explicitly approved them.
- After editing, report changed files and commands run.
" \
  --allowedTools "Read,Edit,Write,Bash(git diff*),Bash(uv run pytest*),Bash(uv run ruff*),Bash(uv run mypy*),Bash(uv run flake8*)" \
  --max-turns 25 \
  --output-format json
```

Review template:

```bash
git diff main...HEAD | claude -p "
Review this Storyteller diff. Focus on bugs, missed tests, prompt/agent regressions, async issues, DB/converter risks, and overengineering. Return blocking findings first, then non-blocking notes.
" \
  --allowedTools "Read" \
  --max-turns 3
```

Guardrails:
- Do not use `--dangerously-skip-permissions` by default; prefer scoped `--allowedTools`.
- Do not trust Claude output blindly: inspect changed files and run relevant verification before completing or blocking the Kanban card.
- If `claude -p` fails because of auth, rate limits, or tool permissions, continue with Hermes tools and mention the failure in the handoff.

### Parallel execution via git worktrees

When a task decomposes into **independent** units of work (different modules, no shared file edits, no ordering dependency), run them in parallel via isolated git worktrees rather than sequentially:

- Use the Agent tool with `isolation: "worktree"` for each parallel unit, or `TeamCreate` for fan-out across multiple sub-agents. Each worktree returns its path + branch.
- After all parallel units finish, consolidate the changes into a single feature branch (`feat/<topic>` or `fix/<topic>`), resolve any cross-worktree conflicts there, then open **one PR** with all the changes.
- Use sequential execution when units genuinely depend on each other (one's output feeds another, shared file edits, ordering-sensitive tests). Don't fabricate parallelism by forcing real dependencies into separate worktrees.
- If `isolation: "worktree"` and `TeamCreate` are unavailable in the current harness, fall back to sequential execution on a single feature branch rather than skipping the consolidation rule.

### Demo Contract — what to ship at the end

The assistant picks the demo form based on what the change touches (multiple may apply):

| Change touches                                                   | Demo                                                                                  |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Backend / engine / db / knowledge / timeline / models            | PR link + green CI gauntlet (ruff, format, flake8, mypy, pytest).                     |
| `interfaces/web/`, admin dashboard                               | Boot the app, exercise the feature, paste screenshots in the PR.                      |
| `cast/`, `prompts/`, narrative-affecting engine paths            | Run deterministic benchmarks via the `run-benchmarks` skill, post before/after.       |
| `db/migrations/` (alembic)                                       | Run `alembic upgrade head` against a scratch DB; paste the affected table schema.     |
| `research/` (Wikipedia client and similar live integrations)     | Recorded request/response or stubbed integration run — CI green alone is insufficient.|
| `benchmarks/scenarios/` additions                                | Run the new scenario once, post the rubric output in the PR.                          |
| `tests/`-only changes                                            | Green CI is sufficient — no further demo.                                             |
| `docs/`, `.claude/`, `CLAUDE.md`, `README*`                      | PR link only — no demo expected.                                                      |

Git workflow from the section above still applies: short-lived branch → PR with `gh pr create` → merge to trunk when green and low-risk; never direct push to `main` unless Max explicitly says so.

### Escalation to feature-factory (opt-in)

Run `/feature-factory <idea>` (Researcher → Story → Spec → parallel QA review) **only** when *any* of these apply, and ask the user to confirm before starting it:

- Touches any `PromptSection` or `required_vars` — prompt-variable wiring has silently broken before.
- Adds a model field that a downstream consumer is expected to read in the *same* change (the `NPCCard.known_names_for_player` → Narrator-prompt regression class: supplier-side test passing ≠ consumer-side wiring exists).
- Edits a prompt in either `prompts/*_en.py` or `prompts/*_ru.py` without an equivalent edit to its locale pair (locale-parity drift).
- Cross-cuts ≥ 3 of `cast/`, `engine/`, `prompts/`, `db/`, `knowledge/`, `timeline/`, `models/`, `interfaces/`, `research/` — *or* touches both `cast/` and `prompts/` in the same change.
- Introduces a new agent, a schema migration, or a release-affecting change.
- Touches anything covered by an accepted decision record in `docs/decisions/` or `docs/studio/09-founder-decision-register.md`.

The user can always force factory with `factory <idea>` or `/feature-factory <idea>`, or suppress escalation for one task with "stakeholder mode" / "just do it".

The `decision-records` skill is still required for the boundary changes listed in the Git Workflow section; invoke `/decision-records` between implementation and `gh pr create`. PR-time gates (`simplify`, `pr-review-toolkit:review-pr`, `decision-records`, `prompt-audit`) remain unchanged.

## Testing

- For bug fixes, follow strict TDD: write the regression test first, **run pytest and watch it fail with the expected assertion error**, then fix the root cause and watch the same test pass. A test you never saw fail is not a regression test — it might be exercising the wrong path or asserting the wrong thing. Don't patch around symptoms.
- Test at the consumer-side integration seam, not just the supplier. A test that asserts a model method returns the right value does not prove the consumer actually uses it. When a contract says "*X receives Y*", add a test that reads X's input boundary and asserts Y appears there. Past regressions in this repo (NPC alias list reaching `NPCCard.known_names_for_player` but never reaching the Narrator's prompt body) all lived in this gap — supplier well-tested, consumer wiring un-tested.
- Maintain 90%+ unit test coverage. When adding new modules, add tests in the same PR.
- E2E tests under `tests/e2e/` must carry Allure annotations following the project taxonomy.
- **Mutation testing:** PRs that touch the mutation scope — `models/`, `timeline/`, `knowledge/` (minus the LLM-driven `memory.py` / `scene_consolidation.py` / `scene_summary_phase.py`), `db/converters/`, `cast/dice.py`, or `config.py` (the deterministic core; ADR-0005 expanded this from the original `models/`+`timeline/` pilot of ADR-0004) — run `mutmut` on the full scope and must clear the mutation-score threshold.
  - **Threshold:** 95% (baseline 97.33% = 1789/1838, Linux nightly run 26643646713; threshold = floor(baseline) − 2 for run-to-run noise). Score is `killed / (killed + survived)` from `mutants/mutmut-cicd-stats.json`.
  - **Async tests are deselected** from mutmut's pytest invocations via `-m "not db and not benchmark and not asyncio"` in `[tool.mutmut].pytest_add_cli_args`. mutmut runs pytest in-process, where `pytest_asyncio`'s event-loop-policy teardown raises `TypeError: loop must be an instance of AbstractEventLoop` and aborts the stats phase (`killed=0`). The mutated modules are pure and densely covered by sync tests, so this preserves the kill signal.
  - **Run locally:** `uv run mutmut run --max-children 4 && uv run mutmut export-cicd-stats && cat mutants/mutmut-cicd-stats.json`.
  - **macOS gotcha:** the bare `Run locally` recipe segfaults under `os.fork()` against the project's C-extension stack on Python 3.14. Pin Python 3.11 and disable fork-safety. One-time setup: `UV_PROJECT_ENVIRONMENT=.venv-mutmut uv sync --python 3.11 --group dev --extra openai --extra anthropic`. Then run: `UV_PROJECT_ENVIRONMENT=.venv-mutmut env OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES uv run --python 3.11 mutmut run --max-children 4 && UV_PROJECT_ENVIRONMENT=.venv-mutmut uv run --python 3.11 mutmut export-cicd-stats && cat mutants/mutmut-cicd-stats.json`.
  - **macOS stats-phase abort:** beyond the segfault, macOS often cannot complete mutmut's in-process stats phase at all (the `pytest_asyncio` teardown `TypeError` above), failing for *any* scope — even the green pilot. The Linux nightly is the authoritative oracle; validate local test *selection* with plain `python -m pytest`, not mutmut. **Never run `uv`/`pytest` with cwd inside `mutants/`** — it builds a nested venv from the mutated tree and yields bogus `ModuleNotFoundError`; and never run two `mutmut run` jobs concurrently in one worktree (they share `mutants/`).
  - **Missing-module errors:** if mutmut raises `ModuleNotFoundError` or `FileNotFoundError`, add the missing path to `[tool.mutmut].also_copy`.
  - **Ratchet:** a nightly full run (`.github/workflows/mutation-nightly.yml`) uploads the report as an artifact; bump the threshold only after several nights of higher scores.
  - **Run on demand in CI** (any branch, no local setup): `gh workflow run mutation-nightly.yml --ref <branch>` or `gh workflow run ci.yml --ref <branch>` (the latter runs the full CI including the mutation job in report-only mode). Watch with `gh run watch`. Download the report artifact with `gh run download --name mutmut-full-report` (nightly) or `--name mutmut-report` (ci.yml).

## Working Style

Adapted from [andrej-karpathy-skills/CLAUDE.md](https://github.com/forrestchang/andrej-karpathy-skills/blob/main/CLAUDE.md). Bias toward caution over speed; use judgment for trivial tasks.

### 1. Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask. (See "Default workflow: stakeholder mode → Ambiguity rule" for the load-bearing-vs-cosmetic split that governs *when* to interrupt.)

### 2. Simplicity First
Minimum code that solves the problem. Nothing speculative.
- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.
- Ask: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes
Touch only what you must. Clean up only your own mess.
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
- Remove imports/variables/functions that *your* changes made unused; don't remove pre-existing dead code unless asked.
- Test: every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution
Define success criteria. Loop until verified.
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"
- For multi-step tasks, state a brief plan with a verification check per step.
- Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.
