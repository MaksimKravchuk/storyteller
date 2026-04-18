---
name: run-benchmarks
description: Run deterministic narration benchmarks to detect regressions in narrative-critical code. Use when a diff touches `cast/`, `prompts/`, `engine/`, `research/`, `timeline/`, `knowledge/`, `llm/`, or `benchmarks/` itself, and the user wants to verify narrative quality before merging. Opt-in — hits paid LLMs.
context: fork
allowed-tools: Bash, Read, Grep, Glob
---

# Run narration benchmarks on relevant changes

The repo ships a deterministic benchmark harness that drives the engine through fixed scenarios, scores narration against an ISU-style rubric, and archives the report as JSON + markdown. Use it to catch narrative regressions that unit tests can't see.

This skill is **opt-in** — benchmark runs hit paid LLMs (OpenAI and Anthropic) and take a few minutes each. Always confirm with the user before invoking.

## Step 1: Decide whether a benchmark run is warranted

Check what changed:

```bash
git diff --name-only $(git merge-base HEAD main)..HEAD
# or, for uncommitted work:
git diff --name-only
```

Benchmarks are worth running when the diff touches any of:

- `cast/` — Director, actors, narrator, scene_builder, NPC generator, memory manager
- `prompts/` — any PromptTemplate or PromptSection changes
- `engine/` — public API or factory wiring
- `research/` — Wikipedia client (affects DataMiner outputs)
- `timeline/` — EventManager, time costs
- `knowledge/` — graph scoping or query logic
- `llm/` — provider clients, model routing
- `benchmarks/` — harness, scoring, or scenario definitions themselves

Skip if the diff is purely in `db/`, `interfaces/`, `models/` without behavioral shift, or docs/tests.

## Step 2: Pick the right scenario

Three scenarios are registered (`benchmarks/scenarios/_registry.py`):

| Scenario id | When to run |
|---|---|
| `memory_follow_up_marcus` | MemoryManager, NPC recall, conversation continuity, dialogue history |
| `escalation_guard_assault` | NPC hostility, combat, dice, escalation logic, guard/authority NPCs |
| `autonomy_three_guards_tavern` | NPC autonomy, moods, crowd behavior, ambient dialogue |

If the change is broad (Director, Narrator, prompts shared across agents), run all three. For a narrow change, pick the one that exercises the affected subsystem.

## Step 3: Run the benchmark

```bash
# Single scenario, one iteration (fastest — ~1-3 min, a few dollars)
uv run python -m benchmarks run --scenario memory_follow_up_marcus --iterations 1

# All scenarios
uv run python -m benchmarks run --iterations 1
```

Results archive to `benchmarks/results/` as `<timestamp>_<sha>_<scenario>_iter<N>.{json,md}`.

## Step 4: Compare against a baseline

Find the most recent archived result for the same scenario from before the change:

```bash
ls -t benchmarks/results/*memory_follow_up_marcus_iter0.json | head -5
```

Pick one from a commit before your branch diverged and diff:

```bash
uv run python -m benchmarks compare <baseline.json> <current.json>
```

The compare command highlights per-rubric score deltas. Read the markdown report alongside it (`benchmarks/results/<same-stem>.md`) for qualitative shifts — judges often flag narrative issues that the score aggregate smooths over.

## Step 5: Report to the user

Summarize:

1. **Which scenario(s) ran** and why you picked them.
2. **Score deltas vs baseline** — call out drops of >0.5 on any rubric element.
3. **Qualitative notes** from judge transcripts when scores shifted.
4. **Verdict** — regression, neutral, or improvement, with file:line pointers if the change is the likely cause.

If scores regressed, recommend either a fix before merge or a second run with more iterations to rule out LLM noise (benchmarks are non-deterministic even with fixed scenarios).

## Notes

- The harness uses a 6-model judge panel by default (`benchmarks/harness/panel.py`). `--judges` or `--max-judges` let you trim cost at the price of signal.
- Never auto-run without user approval — the full suite costs several dollars per pass.
- If `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` aren't set, the run will fail fast; surface that to the user rather than working around it.
