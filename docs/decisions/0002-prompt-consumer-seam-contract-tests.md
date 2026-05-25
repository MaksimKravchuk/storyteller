# ADR-0002: Prompt-template consumer-seam contract tests

Date: 2026-05-25
Status: Accepted
Decision owner: Max
Related: ADR-0001, GitHub #276, `tests/prompts/test_consumer_seam_contract.py`, `prompts/base_template.py`, `CLAUDE.md` "Testing" section

## Context

`PromptTemplate.render` in `prompts/base_template.py` intentionally **silently skips** any `PromptSection` whose `required_vars` are not all present in the kwargs:

```python
for section in self._sections:
    if all(required_var in kwargs for required_var in section.required_vars):
        parts.append(section.render(**kwargs))
```

This is load-bearing for the design — sections that depend on optional context (e.g. Actor `_MEMORY` only for NPCs with memories, Narrator `world_mood` only on new scenes) drop without crashing the call. But the same property is **a silent failure mode** when a consumer agent forgets to populate a section's required vars: the LLM gets a plausible-looking but incomplete prompt, no exception fires, and the regression ships.

This failure class is documented:

- `CLAUDE.md` → "Testing": the `NPCCard.known_names_for_player` regression — supplier well-tested, consumer wiring un-tested — lived exactly in this gap.
- ADR-0001 → "Context": the same example is named as the motivation for the upstream feature-factory chain.

The existing `tests/test_prompt_localization.py:_assert_section_parity` guards EN/RU locale skew (drop-in template replaceability), but does **not** check that the consumer agent populates every section's vars on a real `act()` call.

## Decision

Add a per-performer **consumer-seam contract test suite** in `tests/prompts/test_consumer_seam_contract.py` that for every critical performer:

1. Constructs a **maximal** game-state fixture so every `PromptSection`'s `required_vars` — including intentionally optional ones (Actor memory/hostility/goal, Narrator world_mood, SceneBuilder persistent_world_changes/known_object_states, Director scene_history) — has its preconditions satisfied by real data on the game state.
2. Drives the performer's `act()` through a mocked LLM.
3. Captures the system prompt actually sent to the LLM via `llm_client.send_message.call_args.kwargs["system_prompt"]` (the seam `cast/base_performer_class.py:_call_llm` writes to).
4. Re-renders each `PromptSection` individually against the same context and asserts every rendered section appears in the captured prompt.

The suite covers all five critical performers (Narrator, Actor, NPCGenerator, Director, SceneBuilder) in both English and Russian locales (12 contract cases), plus two `TestContrivedBugIsCaught` cases that prove the assertion is load-bearing by monkey-patching `Actor.set_context` to drop a required var and observing the assertion fire.

`PromptTemplate.render` keeps its silent-skip semantics — no `render_strict` is added.

## Rationale

- **Catches the documented regression class.** A consumer who forgets to call `set_context(physical_status=...)` makes both Actor `constraints` and `output_dialogue` sections silently drop. The contract test fails with a locatable error message: `PromptSection 'constraints' missing from rendered prompt — consumer-seam regression: a required var was not populated by the consumer agent.`
- **Tests the seam that breaks, not the supplier.** Per CLAUDE.md Testing section: "Test at the consumer-side integration seam, not just the supplier." This suite reads `send_message.call_args.kwargs["system_prompt"]` — the boundary the LLM actually sees — and asserts every section is there.
- **Maximal fixture, not minimal.** A minimal-context test would either fail on intentionally-optional sections (false positive) or be neutered to "skip is OK" (defeating the regression class). The maximal fixture proves: "if the data exists in game state, the consumer wires it onto every section."
- **No production code change.** `PromptTemplate.render`'s silent-skip semantics are intentional for adaptive partial-context rendering. Test-side detection is the cheapest gate; a strict variant would either be unused (test-only) or break working partial-context paths.

## Alternatives considered

### Alternative 1: AST-based static check across all `*.render(...)` callsites

Walk the codebase with `ast`, find every `*.render(...)` callsite, statically link it to its template, and assert the kwargs cover all `required_vars`.

Rejected as the **initial** implementation because: (a) kwargs are frequently constructed at runtime via `**dict_var` — a static walker would need to model dataflow to recover the dict's keys, which is fragile; (b) `set_context` is called accross many sites with conditional `if` guards that resolve at runtime; (c) the surface "what's a render of a `PromptTemplate`?" is not statically distinct from `.render(...)` on unrelated objects.

Kept as a follow-up option: once Option 2 stabilizes the regression class and the test fixtures encode the consumer-side contract, an AST checker can be added as a secondary, fast gate. Not in scope for #276.

### Alternative 2: `render_strict` that raises on missing vars

Add `PromptTemplate.render_strict()` that raises `ValueError` on any missing required var. Use it in tests (production keeps `render` semantics).

Rejected because: every contract test already needs to construct a maximal fixture and drive `act()`. With the LLM mocked and the prompt captured, the section-presence assertion is equivalent to `render_strict` for the test's purposes — and avoids adding a parallel API to `PromptTemplate`. Skipped per CLAUDE.md "Simplicity First": no abstraction for single-use code.

### Alternative 3: Status quo (rely on prompt-wiring-auditor PR-time agent)

The `prompt-wiring-auditor` PR-time gate (ADR-0001) catches the same regression class on the post-hoc PR diff.

Rejected as the **only** gate because: PR-time review is the last line of defence, not the first. A consumer-seam regression that slips past PR review (busy reviewer, plausible-looking prompt, no obvious diff symptom) ships with no other guard. Local pytest catches it on the first re-run after a refactor — the earliest possible signal.

## Consequences

### Positive

- Every contributor adding a new performer or PromptSection now has a parametrized test slot to drop into — the future-agent-guardrail block in this ADR's section below names that workflow.
- The contract failure message includes the offending section name, so future regressions diagnose in seconds rather than minutes of prompt diff-staring.
- The test runs in ~50ms — no real LLM calls, no DB — so it lives in the standard pytest path with no opt-in flag.

### Negative

- Test data drift: when an existing `PromptSection`'s `required_vars` change, the maximal-fixture builder must be updated to satisfy the new requirement. This is the **intended** failure mode — a `required_vars` addition without a corresponding consumer update is the exact regression class the suite catches, and the test should fail at that point.
- Five performers × two locales = 10 parametrized cases for the system prompts alone. Adding a sixth performer adds two cases. The combinatorics are linear in performer count, which is the correct fan-out.

## Verification

- All 14 contract tests pass: 10 system-prompt cases + 2 NPCGenerator user-message cases + 2 contrived-bug demonstrations.
- Manually contrived regression (`cast/narrator.py`: drop `player_appearance` kwarg) reproduces a clean failure: `AssertionError: PromptSection 'player_character' missing from rendered prompt — consumer-seam regression: a required var was not populated by the consumer agent.` Restoring the kwarg returns all 14 tests to green.
- The full gauntlet (ruff, format, flake8, mypy, pytest) passes with the suite in place.

## Future-agent guardrails

**When adding a new `BasePerformer` subclass that takes a `PromptTemplate`:**

1. Add a `PerformerCase` entry to `_CASES` in `tests/prompts/test_consumer_seam_contract.py` covering both `"English"` and `"Russian"` locales.
2. Add a section-kwargs builder that **mirrors** the consumer's `set_context` calls — including conditional / optional sections. Read the consumer's `act()` (and any helpers it calls) and reverse the conditions.
3. Extend `_build_maximal_game_state()` if your performer needs new game-state preconditions to satisfy a new section's required vars (e.g. new world-state fields, new scene-action types).

**When adding a new `PromptSection` to an existing template:**

- If the section is **always-on**, update both the consumer's `set_context` block AND the corresponding section-kwargs builder in this test file. Both EN and RU.
- If the section is **optional**, gate it in the consumer (so partial-context turns still render the rest), and update the section-kwargs builder so the maximal fixture sets the var — the contract test asserts the optional section *does* render when its data exists.

**Do not** add `# noqa` or `# pragma: no cover` to suppress a contract test failure. The failure is the signal — refactor the consumer or update the fixture.
