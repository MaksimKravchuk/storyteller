# ADR-0004: Mutation-testing pilot scoped to `models/` + `timeline/` with a ratcheted CI gate

Date: 2026-05-28
Status: Accepted
Decision owner: Max
Related: PR #294 (pilot introduction), PR #296 (score raised 79.8% → 96.6%), `docs/decisions/0002-prompt-consumer-seam-contract-tests.md`, `docs/decisions/0002-benchmark-auto-compare-and-ratchet.md`, `CLAUDE.md` (Testing → Mutation testing section); **extended by `docs/decisions/0005-mutation-testing-deterministic-core-expansion.md`** (scope grown to the full deterministic core, threshold recalibrated to 95)

## Context

Storyteller already enforces line coverage (90%+) and consumer-seam contract tests (ADR-0002 *prompt-consumer-seam*). But line coverage answers "was this line executed?", not "would a test notice if this line were wrong?" The repo has a documented history of exactly that gap — supplier-side code well-covered while the consumer wiring that reads it was untested (the `NPCCard.known_names_for_player` → Narrator-prompt regression). Coverage was green throughout that class of bug.

Mutation testing closes that gap: it perturbs the source (flip `<` to `<=`, swap `and`/`or`, change a default, blank a string) and asks whether any test fails. A surviving mutant is a line that runs under test but whose *behavior* nothing asserts. The question was whether to adopt it, and — because mutation testing is slow and noisy at repo scale — at what scope and with what gate, so it strengthens the suite without becoming a flaky tax on every PR.

`models/` and `timeline/` were chosen as the pilot surface because they are the deterministic, logic-dense core (clock math, event windows, effect application, memory-write field wiring, domain invariants) where a survived mutant maps cleanly to a missing behavioral assertion — unlike LLM-driven code, where "correctness" needs a judge, not an `assert`.

## Decision

Adopt `mutmut` as a mutation-testing gate, scoped to a pilot, with a calibrated, ratcheted threshold:

1. **Pilot scope.** `pyproject.toml [tool.mutmut]` sets `paths_to_mutate = ["models/", "timeline/"]` with `mutate_only_covered_lines = true`. The rest of the tree is `also_copy`'d so imports resolve but is not mutated.
2. **Score metric.** `killed / (killed + survived)` from `mutants/mutmut-cicd-stats.json` (via `mutmut export-cicd-stats`). Equivalent/segfault/skip statuses are excluded from the denominator.
3. **Threshold = 77, calibrated as `floor(baseline) − 2`.** The introduction baseline was 79.8% (540/677). The −2 absorbs run-to-run noise so a green suite does not flap red. The gate fails a PR when the score drops below 77.
4. **Gate runs only on pilot-scope *source* changes.** The `mutation` job in `.github/workflows/ci.yml` first detects whether the PR diff touches `models/*.py` / `timeline/*.py` (excluding `**/__init__.py`); if not, `in_scope=false` and the run is skipped (green). A tests-only or docs PR does not pay the mutmut cost.
5. **Nightly full-scope run is report-only.** `.github/workflows/mutation-nightly.yml` runs the whole pilot on a schedule (and on `workflow_dispatch`), never gating, and uploads both the aggregate stats and the surviving-mutant list (`mutants/survivors.txt`) as an artifact.
6. **Ratchet policy: bump the threshold only after sustained nightly improvement** — never off a single lucky run. The threshold tracks `floor(baseline) − 2`; the baseline moves only when several consecutive nightlies clear a higher score.
7. **Survivors obey the suppression ban.** `CLAUDE.md` forbids `# noqa` / `# pragma: no cover` / `# type: ignore`. A genuinely equivalent mutant is therefore handled by *behavior-preserving source refactor* or by *accept-and-document*, never by suppression. A survivor that is killable in principle but unreachable by mutmut's own test selection is documented as such, not chased.

## Rationale

- **Coverage proved insufficient; mutation testing targets the exact failure class.** The pilot's first real exercise (PR #296) lifted the score 79.8% → 96.6% purely by *adding behavioral assertions to already-covered lines* — every kill was a line that ran under test but asserted nothing about its result. That is precisely the supplier-covered/consumer-unasserted gap ADR-0002 (*prompt-consumer-seam*) exists to fight, caught mechanically.
- **`mutate_only_covered_lines = true` keeps the signal clean but has a denominator trap.** Mutating only covered lines means the score reflects assertion strength, not coverage gaps (those are the line-coverage gate's job). The trap: adding a test that covers a *previously-uncovered* line *adds* mutants to the pool, so coverage expansion can fail to move — or even lower — the score. The cheap, denominator-safe kills are stronger assertions on already-covered lines; that is the intended way to raise the score.
- **`floor(baseline) − 2` is the honest threshold.** Mutation runs are not perfectly deterministic at this scale (see the macOS fork note below), and the score shifts by a mutant or two between runs. Gating exactly at the baseline would flap; −2 is a noise margin, mirroring the variance-aware posture of the benchmark ratchet (ADR-0002 *benchmark-auto-compare*).
- **Scoping the gate to source changes keeps it cheap and non-annoying.** A full pilot run is minutes of paid-ish CI; running it on every tests/docs PR would be pure tax. Gating only when pilot *source* changes ties the cost to the risk (a behavior change is what could regress kill-rate), while the nightly keeps a full-scope read-out without blocking anyone.
- **Equivalent mutants are a fact of mutation testing, not a bug to suppress.** A `.get(k, "")` → `.get(k, None)` change where the value only feeds a falsy guard is genuinely indistinguishable by any test. The suppression ban forces the honest dispositions — refactor the breeding construct, or document it — rather than papering over it with an inline ignore.

## Alternatives considered

### Alternative 1: Don't adopt mutation testing; rely on line coverage + consumer-seam tests

Keep the 90% coverage gate and ADR-0002 (*prompt-consumer-seam*)'s consumer-seam discipline as the only test-quality bars.

Rejected because: both are necessary but neither answers "would a test catch a wrong value here?" The known regression class slipped past green coverage. Mutation testing is the only one of the three that mechanically finds unasserted-but-executed logic.

### Alternative 2: Mutate the whole repo from day one

Run `mutmut` across `cast/`, `engine/`, `prompts/`, `db/`, etc.

Rejected because: (a) much of the value-bearing code is LLM-driven, where a survived mutant does not map to a missing `assert` — it needs a judge, which is the benchmark harness's job, not mutmut's; (b) a full-repo run is far too slow to gate a PR; (c) the noise of equivalent mutants across the whole tree would bury the signal. A deterministic, logic-dense pilot proves the approach and produces actionable kills first.

### Alternative 3: Gate at the exact baseline (79–80%), no noise margin

Set the threshold to the measured baseline and require the suite to never drop below it.

Rejected because: mutation scores are not bit-stable run-to-run, so an exact-baseline gate would flap red on noise alone and erode trust in the gate. `floor(baseline) − 2` is the smallest honest margin.

### Alternative 4: Auto-ratchet the threshold on every green run

Raise the threshold automatically whenever a run scores higher.

Rejected because (same reasoning as ADR-0002 *benchmark-auto-compare*'s auto-pin rejection): it would ratchet on a single lucky run against known variance and remove the human checkpoint. The threshold bumps only after *sustained* nightly improvement, deliberately.

## Consequences

Positive consequences:
- The deterministic core now has a mechanical assertion-strength gate, complementing coverage and consumer-seam tests.
- PR #296 demonstrated the pilot produces concrete, high-value kills (clock boundaries, event-window logic, effect-memory field wiring, npc-id resolution) and reached 96.6% tests-only.
- The nightly survivor-list artifact makes future triage cheap — no full local re-run needed to see *which* mutants survive.
- Gate cost is tied to risk: tests/docs PRs skip it entirely.

Tradeoffs / risks:
- **Equivalent mutants set a practical ceiling below 100%.** `.get(k, "")`→`.get(k, None)` (value only feeds a falsy guard), `"local"`→`"LOCAL"` before `.upper()`, and dropped kwargs equal to a model field default are unkillable by any test. They are expected residue, not failures.
- **mutmut's per-mutant test selection has a blind spot.** With coverage-context selection, a mutant on a function-*signature* default argument (e.g. `get_attribute(default: int = 0)` → `1`) attributes its coverage to import time, so the asserting call-site test is never run against it — it survives despite a correct, passing regression test. This is a tooling limitation, not a test gap, and is documented rather than chased.
- **macOS local runs are flaky.** The `os.fork()` segfault against the C-extension stack is *nondeterministic* even with the documented `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` + Python 3.11 recipe; a re-run over an existing `mutants/` dir can cache all-segfault. Reliable local fallback is `--max-children 1` after `rm -rf mutants`; the authoritative read is the Linux nightly. (Captured in the agent memory `mutmut-local-gotchas`.)

What future agents must preserve:
- **The score metric is `killed / (killed + survived)`** from `mutants/mutmut-cicd-stats.json` — do not redefine it to include equivalent/segfault statuses in the denominator.
- **The threshold is `floor(baseline) − 2` and moves only on sustained nightly improvement.** Do not raise it off a single run; do not lower it to make a red PR pass.
- **Do not satisfy the gate by suppression.** No `# noqa` / `# pragma: no cover` / `# type: ignore`, and do not add equivalent mutants to a mutmut ignore. Refactor (behavior-preserving) or document.
- **Prefer kills via stronger assertions on already-covered lines.** Because `mutate_only_covered_lines = true`, do not chase score by covering new lines — that grows the denominator and can lower the score.
- **Keep the PR gate scoped to pilot *source* changes** and the nightly **report-only**. Do not make the nightly gate, and do not run the full pilot on every PR.
- **Expanding the pilot scope beyond `models/` + `timeline/` is a new decision** — supersede or extend this ADR, and recalibrate the baseline/threshold for the new scope before gating on it. (Done in ADR-0005: scope grown to the full deterministic core; threshold recalibrated to 95 off a 97.33% Linux baseline.)

## Verification / tests

- `pyproject.toml [tool.mutmut]` — `paths_to_mutate`, `mutate_only_covered_lines = true`, `also_copy`, `do_not_mutate`.
- `.github/workflows/ci.yml` (`mutation` job) — scope detection over `models/*.py` / `timeline/*.py` (excluding `**/__init__.py`), `export-cicd-stats`, the `TOTAL_CHECKED == 0` guard, and the `THRESHOLD: "77"` gate (PR-only).
- `.github/workflows/mutation-nightly.yml` — full-scope, report-only, uploads `mutmut-cicd-stats.json` + `survivors.txt`.
- `CLAUDE.md` → Testing → "Mutation testing (pilot)" — the local recipe, macOS gotcha, missing-module remedy, and ratchet/on-demand instructions.
- Reproduce locally (macOS): the pinned-Python-3.11 + fork-safety recipe in `CLAUDE.md`; for a flake-free number dispatch the nightly on the branch (`gh workflow run mutation-nightly.yml --ref <branch>`).
- Evidence the pilot delivers: PR #296 raised the score to 96.6% (655/678) purely via added tests, no source change. The figure is Linux-confirmed via a manual nightly dispatch on the branch (`mutation-nightly.yml` run 26605806002: 655 killed / 678 checked); PR #296's own `mutation` gate job correctly *skipped*, since the PR touches no pilot-scope source — which is itself the source-scoped-gate behavior working as designed.

## Related files

- `pyproject.toml`
- `.github/workflows/ci.yml`
- `.github/workflows/mutation-nightly.yml`
- `CLAUDE.md`
- `models/`, `timeline/`
- `tests/test_effect_memory_internals.py`, `tests/test_effect_emit_memory.py`, `tests/test_effect_applier.py`, `tests/test_event_manager.py`, `tests/test_time_costs.py`, `tests/test_memory_slots.py`, `tests/test_models.py`, `tests/test_models_game.py`
