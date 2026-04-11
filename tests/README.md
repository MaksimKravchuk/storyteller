# Tests

Storyteller is AI-developed, so we rely on automated tests — both for regression protection and as executable product spec. The test suite is split into two layers:

- **Unit tests** — fast, deterministic, run on every push. Target ≥90% line coverage.
- **End-to-end tests** — subprocess-driven CLI scenarios with `TesterAgent` verification. Require `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`.

## Running tests

```bash
# Unit tests (fast; enforces 90% coverage floor)
uv run pytest tests/ --ignore=tests/e2e -v

# Unit tests with coverage report in the terminal
uv run pytest tests/ --ignore=tests/e2e --cov --cov-report=term-missing

# A single test file or test
uv run pytest tests/test_dice.py -v
uv run pytest tests/test_dice.py::TestCombatOutcomeCategories::test_npc_overpowers -v

# E2E tests (slow; real LLM calls)
uv run pytest tests/e2e/ -v
```

## Coverage standard

- Floor is **90%** line coverage, enforced by `fail_under = 90` in `pyproject.toml:[tool.coverage.report]`.
- CI measures coverage on every PR and posts per-module numbers as a comment.
- Packages under the floor have dedicated follow-up work — see the "Coverage gaps" section in `.claude/plans/structured-mixing-toast.md` for the backlog.

## Allure: reading tests as spec

Every unit test carries four Allure decorators:

```python
import allure

@allure.epic("Combat & Action Resolution")
@allure.feature("Combat dice")
class TestCombatOutcomeCategories:
    @allure.story("Outcome categories")
    @allure.title("NPC with +10 skill rolling 18 vs player 5 overpowers the player")
    def test_npc_overpowers(self): ...
```

**This is enforced at collection time.** `tests/conftest.py:pytest_collection_modifyitems` fails any non-e2e test missing `epic` / `feature` / `story` / `title`. The error message points you to `tests/TEST_TAXONOMY.md`, which contains the full epic/feature table — **look up your test file there before writing labels**.

### Render Allure locally

```bash
# Collect results
uv run pytest tests/ --ignore=tests/e2e --alluredir=./_allure

# Render and serve (needs the `allure` CLI — `brew install allure` on macOS)
allure serve ./_allure
```

Open the **Behaviors** tab — you should see a three-level tree `epic → feature → story` with a sentence-form title at each leaf. If the tree looks like a package index or the leaves read as `test_foo_bar`, the labels are wrong.

### Adding a new test

1. Open `tests/TEST_TAXONOMY.md` and find (or add) your test file in the feature map.
2. Copy the epic + feature exactly.
3. Pick a story label (reuse existing ones from sibling tests when possible).
4. Write a sentence-form title that describes the behavior, not the test function name.
5. Run `uv run pytest tests/<your_file>.py -v` — collection will fail loudly if you forget a label.

## Layout

| Path | Purpose |
|---|---|
| `tests/test_*.py` | Unit tests (flat layout, grouped in Allure by epic/feature). |
| `tests/conftest.py` | Shared fixtures (`loguru_sink`, `simple_setting`, `empty_graph`, `populated_graph`) + Allure enforcement hook. |
| `tests/director_helpers.py` | `make_director`, `make_game_state`, `make_mock_agent`, `setup_npc`. Use these before hand-rolling Director test setup. |
| `tests/base_performer_helpers.py`, `tests/base_performer_nested.py` | Shared mocks for BasePerformer / call-chain tests. |
| `tests/_db_stubs.py` | Stubs `db.engine` in `sys.modules` so unit tests don't open real database connections. |
| `tests/e2e/` | Subprocess-based CLI tests. Separate conftest; **not** subject to the unit-test enforcement hook. |
| `tests/TEST_TAXONOMY.md` | Allure epic/feature reference. Source of truth for labels. |
