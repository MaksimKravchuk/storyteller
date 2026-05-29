# ADR-0005: Expand mutation testing from the `models/`+`timeline/` pilot to the full deterministic core

Date: 2026-05-29
Status: Accepted
Decision owner: Max
Related: extends `docs/decisions/0004-mutation-testing-pilot.md`; `pyproject.toml` (`[tool.mutmut]`), `.github/workflows/ci.yml` (`mutation` job), `.github/workflows/mutation-nightly.yml`, `CLAUDE.md` (Testing → Mutation testing), branch `feat/mutmut-expand-deterministic-core`

## Context

ADR-0004 adopted `mutmut` as a ratcheted mutation-testing gate but deliberately scoped it to a **pilot** — `models/` + `timeline/` — and explicitly deferred the question of wider coverage: *"Expanding the pilot scope beyond `models/` + `timeline/` is a new decision — supersede or extend this ADR, and recalibrate the baseline/threshold for the new scope before gating on it."* This ADR is that new decision.

The pilot proved the approach: PR #296 lifted the pilot score to 96.6% purely by adding behavioral assertions to already-covered lines — exactly the "executed but unasserted" gap line-coverage cannot see. But the pilot left the rest of Storyteller's **deterministic, logic-dense core** ungated:

- `knowledge/` — the NetworkX graph: edge/flag/index/label round-trips, scope-filtered NPC queries, salience+recency scoring, hearsay/rumor timestamps and reachability walks, subject-identity resolution.
- `db/converters/` — the domain↔ORM bridge: UUID serialisation, scope lowercasing, signed relationship intensity, field preservation. A symmetric or silently-dropped field here is precisely the unasserted-value bug class mutation testing exists to catch.
- `cast/dice.py` — contest/aggression/combat math with an injectable `random.Random` (seedable, so fully deterministic under test).
- `config.py` — provider auto-detection from model name and API-key status.

All four are non-LLM and already unit-tested, so a survived mutant maps cleanly to a missing `assert` — the same property that made `models/`+`timeline/` a good pilot.

Three `knowledge/` modules are **not** deterministic in the relevant sense: `memory.py`, `scene_consolidation.py`, and `scene_summary_phase.py` orchestrate `async` LLM calls (the `MemoryManager` write phases). Per ADR-0004's Alternative-2 reasoning, a survived mutant in LLM-driven code does not map to a missing `assert` — it needs a judge (the benchmark harness), not mutmut. They are kept out of the mutation surface.

Expanding the surface surfaced a tooling bug the narrow pilot never hit. The wider mutated import graph (pulled in by `knowledge/`, `config.py`, and the async performers instantiated by some tests) trips `pytest_asyncio`'s event-loop-policy teardown inside mutmut's in-process `pytest.main()` runner (which force-disables `pytest-randomly`): teardown raises `TypeError: loop must be an instance of AbstractEventLoop` and aborts the stats phase with `killed=0`. Two Linux nightly runs on the branch (`26624204620`, `26626539174`) reproduced this as all-abort before the fix; an early per-file `--ignore` of the first offending test (`tests/prompts/test_consumer_seam_contract.py`) just relocated the crash to the next async test (`test_actor_revealed`) — confirming it is a category problem, not a per-file one.

## Decision

Extend ADR-0004's mutation-testing gate to the full deterministic core, recalibrate the threshold for the new scope, and add a category-level async-test deselection to work around the teardown crash. ADR-0004's **metric, ratchet policy, suppression ban, source-scoped PR gate, and report-only nightly are carried forward unchanged.**

What this ADR **changes**:

1. **Expanded scope.** `pyproject.toml [tool.mutmut].paths_to_mutate = ["models/", "timeline/", "knowledge/", "db/converters/", "cast/dice.py", "config.py"]`, still with `mutate_only_covered_lines = true`.
2. **Exclusions via `do_not_mutate`.** The three LLM-driven knowledge modules — `knowledge/memory.py`, `knowledge/scene_consolidation.py`, `knowledge/scene_summary_phase.py` — are added to `do_not_mutate` (alongside `**/__init__.py`). They are still `also_copy`'d so imports resolve; they are simply not mutated.
3. **Recalibrated threshold = 95**, by ADR-0004's inherited rule `floor(baseline) − 2`. The measured expanded-scope baseline (Linux nightly `26643646713`) is **97.33% = 1789 killed / (1789 killed + 49 survived)**, so `floor(97.33) − 2 = 95`. (5 timeouts are excluded from the denominator, consistent with the unchanged metric.) The `THRESHOLD` env in `ci.yml`'s `mutation` job is updated from `"77"` to `"95"` in the same PR.
4. **Async-test deselection in the mutmut pytest args.** `pytest_add_cli_args` gains `-m "not db and not benchmark and not asyncio"`. `-m` is last-wins, so it supersedes the `addopts` marker expression rather than conflicting. It replaces the abandoned per-file ignore of the consumer-seam test. The deselection applies to all three mutmut pytest invocations (coverage gather, stats, per-mutant).

What this ADR **carries forward from ADR-0004, unchanged** (do not re-litigate):

- The score metric `killed / (killed + survived)` from `mutants/mutmut-cicd-stats.json`; equivalent / timeout / segfault / skip statuses stay out of the denominator.
- The ratchet policy: threshold = `floor(baseline) − 2`, bumped only after **sustained** nightly improvement, never off a single run, never lowered to make a red PR pass.
- The suppression ban (no `# noqa` / `# pragma: no cover` / `# type: ignore`, no mutmut ignore-list for equivalent mutants): handle survivors by behavior-preserving refactor or accept-and-document.
- "Prefer kills via stronger assertions on already-covered lines" (because `mutate_only_covered_lines = true`, covering new lines grows the denominator and can lower the score).
- The PR gate is scoped to mutation-*source* changes; the nightly is report-only. The `ci.yml` diff-scope step now matches `knowledge/*.py`, `db/converters/*.py`, `cast/dice.py`, `config.py` (in addition to `models/*.py`, `timeline/*.py`), excluding `**/__init__.py` and the three LLM-driven knowledge modules.

## Rationale

- **The pilot earned the expansion.** ADR-0004 framed `models/`+`timeline/` as a proof; the proof landed (96.6%, all kills on already-covered lines). The deterministic core beyond the pilot has the identical property — survived mutant ⇒ missing assertion — so withholding the gate from it leaves the exact failure class ADR-0004 targets uncovered in graph, converter, dice, and config logic.
- **`do_not_mutate` is the honest exclusion mechanism.** Dropping the LLM modules from `paths_to_mutate` by path would mean mutating *some* of `knowledge/` and silently omitting three files with no in-config record of why. Listing them in `do_not_mutate` keeps `knowledge/` as the stated unit while documenting the exclusion at the point of truth, and keeps them `also_copy`'d so the rest of `knowledge/` still imports.
- **The async deselection preserves the kill signal — it does not paper over a test gap.** This was the load-bearing thing to verify, not assume. The mutated modules are *pure* and densely covered by **sync** tests (verified via a per-module coverage map on the branch); the async tests that crash teardown target LLM-orchestration and prompt rendering, not the deterministic mutation surface — the same rationale as ADR-0004's existing admin/web/fuzz ignores. Empirically: after the deselection landed, the Linux score *rose* to 97.33%, and the 49 survivors are concentrated in known equivalent / blind-spot classes (see Consequences), not in async-covered code that lost its asserting test. Deselecting async tests removes tests that exercise *LLM-driven* modules, which are out of scope by decision #2 — so no in-scope kill was stranded.
- **A category-level marker beats whack-a-mole per-file ignores.** The crash is a property of *any* async test under mutmut's in-process runner once the import graph is wide enough; the early per-file ignore just moved the crash to the next async test. `-m "... and not asyncio"` deselects the whole category in one stable rule (confirmed locally to deselect all 529 async items and leak none), which is far more durable than chasing individual files.
- **`floor(baseline) − 2 = 95` is the same honest threshold, recomputed for the new scope.** Not invented: it is ADR-0004's rule applied to the measured 97.33% Linux baseline. The −2 noise margin and the "Linux nightly is authoritative, macOS is flaky" provenance posture are inherited verbatim.

## Alternatives considered

### Alternative 1: Keep the pilot at `models/` + `timeline/` only

Leave the gate where ADR-0004 put it and rely on line coverage for the rest of the deterministic core.

Rejected because: ADR-0004 itself scoped the pilot as a proof to be expanded once validated, and the proof landed. The graph, converters, dice, and config carry the same deterministic, assertion-checkable logic; excluding them leaves the targeted failure class ungated there for no principled reason.

### Alternative 2: Mutate all of `knowledge/`, including the LLM-driven modules

Include `memory.py`, `scene_consolidation.py`, and `scene_summary_phase.py` in the mutation surface.

Rejected for ADR-0004 Alternative-2's reasoning: a survived mutant in LLM-orchestration code does not map to a missing `assert` — correctness there needs a judge (the benchmark harness), not a unit assertion. Mutating them would breed noise mutants whose only honest disposition is "needs an LLM to evaluate," which is not what mutmut measures.

### Alternative 3: Keep the per-file `--ignore` for the crashing async test instead of a category marker

Ignore `tests/prompts/test_consumer_seam_contract.py` (and any further offenders) individually.

Rejected because the crash is a category property of async-test teardown under mutmut's in-process runner, not a property of one file: ignoring the first offender just relocated the crash to the next async test. A per-file approach is unstable whack-a-mole; the marker deselection is the category-correct fix.

### Alternative 4: Fix the `pytest_asyncio` teardown crash at the source instead of deselecting

Pin / patch `pytest_asyncio` or restructure the event-loop policy so teardown survives mutmut's in-process runner.

Rejected (for now) because the crash is in third-party teardown under a mutmut-specific execution mode (in-process `pytest.main()` with `pytest-randomly` force-disabled), the async tests contribute no kill signal to the deterministic surface anyway, and a source fix would be speculative effort against tooling we do not control. Deselection is the minimal, signal-preserving workaround. Revisit if async modules ever enter the mutation surface.

## Consequences

Positive consequences:
- The full deterministic core (graph, converters, dice math, config detection) now has a mechanical assertion-strength gate, not just line coverage.
- The expanded baseline is high (97.33% Linux) because the kill commits strengthened assertions on already-covered lines — the intended, denominator-safe way to raise the score.
- The category-level async deselection is a single durable rule, and it fixed the `killed=0` stats abort (two earlier branch nightlies aborted; the post-fix nightly completed with 1789 kills).
- The CI diff-scope step ties mutmut cost to risk across the wider surface: a PR touching only the excluded LLM modules (or only tests/docs) still skips the gate.

Tradeoffs / risks:
- **Equivalent / blind-spot mutants set a practical ceiling below 100%, as in ADR-0004.** After a follow-up kill pass on the `effect_applier` warning branch (see below), ~44 survivors remain, dominated by genuine equivalents: `timeline/effect_applier` falsy-guard defaults (`.get("item", "")` → `.get("item", "XXXX")` / `None` where the value only feeds a falsy branch — e.g. `state_description` flowing into `record_object_state`'s `not state_description` guard, which treats `""` and `None` identically), dropped kwargs equal to a model-field default, `config.py` provider-string variants normalised before comparison, and signature default-arg mutants (mutmut's coverage-context blind spot, attributing coverage to import time). These are expected residue, not test gaps; per the suppression ban they are accept-and-documented, not ignored.
  - **Correction applied: "warning-only" was not equivalence.** An initial pass labelled five `_apply_object_damage` mutants (warning message template + the `location_id`/`target_id` interpolation args on the unknown-location branch) as "equivalent-by-policy / don't-chase loguru." That was wrong — under `mutate_only_covered_lines=true` a survivor sits on a *covered* line, so those were sync-killable via loguru capture, and recording them as equivalent would be suppression-by-rationalization (exactly what the ADR-0004/0005 ban forbids). They are now killed by `test_unknown_location_warning_names_both_ids` (uses the existing `loguru_sink` fixture, asserts the rendered warning starts with the exact template and names both ids twice — verified by manual mutate→fail→restore). Only the two truly-equivalent `state_description` default mutants remain on that handler.
- **Async tests are invisible to mutmut.** This is safe *only* while the mutation surface stays deterministic. If a future change moves an async-covered module into `paths_to_mutate`, the deselection would hide its asserting tests and inflate survivors — that change must revisit Alternative 4 (fix teardown) rather than keep the blanket deselection.
- **macOS local runs still cannot run the stats phase for any scope** (the ADR-0004 fork/asyncio flake). The authoritative read remains the Linux nightly; this is unchanged.

What future agents must preserve:
- **Recalibrate the threshold whenever the scope changes**, using `floor(baseline) − 2` against a **Linux-nightly** baseline. Do not raise it off a single run; do not lower it to pass a red PR. Current: scope = the 4 deterministic areas above; baseline 97.33%; threshold 95.
- **Keep the three LLM-driven knowledge modules out of the mutation surface** via `do_not_mutate`. Adding them is a new decision (revisit Alternative 2 + the async-deselection risk above).
- **Keep the async deselection a category marker** (`not asyncio`), not a growing list of per-file ignores — and only while the surface is deterministic.
- All ADR-0004 invariants still hold: the `killed / (killed + survived)` metric, the suppression ban, kills via stronger assertions on already-covered lines, the source-scoped PR gate + report-only nightly.

## Verification / tests

- `pyproject.toml [tool.mutmut]` — `paths_to_mutate` (6 entries), `mutate_only_covered_lines = true`, `do_not_mutate` (the three LLM modules + `**/__init__.py`), and `pytest_add_cli_args` containing `-m "not db and not benchmark and not asyncio"`.
- `.github/workflows/ci.yml` (`mutation` job) — diff-scope step matches `models/*.py`, `timeline/*.py`, `knowledge/*.py`, `db/converters/*.py`, `cast/dice.py`, `config.py`, excluding `**/__init__.py` and the three LLM modules; `THRESHOLD: "95"` (PR-only gate).
- `.github/workflows/mutation-nightly.yml` — full expanded scope, report-only, uploads `mutmut-cicd-stats.json` + `survivors.txt`.
- **Baseline evidence (Linux, authoritative):** nightly `mutation-nightly.yml` run **26643646713** on `feat/mutmut-expand-deterministic-core` — `killed=1789, survived=49, timeout=5, segfault=0` ⇒ 97.33%. Earlier runs `26624204620` / `26626539174` aborted with `killed=0` (the pre-fix teardown crash); run `26640637171` scored 91.62% mid-kill-work — together they evidence both the crash and the deselection fix.
- Reproduce on demand (flake-free, Linux): `gh workflow run mutation-nightly.yml --ref feat/mutmut-expand-deterministic-core`, then `gh run download --name mutmut-full-report`. macOS local cannot run the stats phase for any scope (ADR-0004 gotcha).
- `CLAUDE.md` → Testing → "Mutation testing" — threshold/scope wording updated to match this ADR (scope = the deterministic core, threshold 95, baseline 97.33%, async-deselect + macOS stats-phase caveats).

## Related files

- `pyproject.toml`
- `.github/workflows/ci.yml`
- `.github/workflows/mutation-nightly.yml`
- `CLAUDE.md`
- `docs/decisions/0004-mutation-testing-pilot.md`
- `knowledge/`, `db/converters/`, `cast/dice.py`, `config.py`, `models/`, `timeline/`
- `tests/` — sync tests strengthened to kill the expanded-scope survivors (commits `81c3268` knowledge, `da2410f` db/converters, `27d52b6` dice+config, `b289af9` re-kill models/timeline)
