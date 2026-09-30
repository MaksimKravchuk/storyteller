# ADR-0018: Default every agent role to gpt-6-luna with reasoning pinned off

Date: 2026-09-30
Status: Accepted
Decision owner: Max (the change alters production spend and player-facing prose; see D004)
Related: ADR-0002 (pinned baselines + ratchet), ADR-0003 (engine temperature pinning), ADR-0013 (judge panel), ADR-0015 (seeded benchmark dice), `docs/studio/09-founder-decision-register.md` D004 (cost budget)

## Context

Before this change the four role models defaulted to a two-tier GPT-5.4 split in `config.py`: `DIRECTOR_MODEL` and `NARRATOR_MODEL` on `gpt-5.4-mini`, `AGENT_MODEL` and `DRAMATURGE_MODEL` on `gpt-5.4-nano`. `OpenAIClient` itself defaulted to `gpt-5.4-mini`.

Three things changed at once:

1. **A cheaper single model is available.** OpenAI's current lineup (GPT-6 Astra / GPT-6.1 Sol / GPT-6 Luna) lists `gpt-6-luna` as the efficient tier at $0.10 input / $0.50 output per 1M tokens, below both GPT-5.4 tiers on both axes. The GPT-5.4 models are no longer in OpenAI's flagship list, though they are not yet on the deprecation schedule. Sources: <https://developers.openai.com/api/docs/models>, <https://developers.openai.com/api/docs/pricing>.
2. **The checked-in price table was wrong.** `costs/model_pricing.py` listed `gpt-5.4-mini` at $0.25 / $2.00 and `gpt-5.4-nano` at $0.05 / $0.40. The corrected standard rates are $0.75 / $4.50 and $0.20 / $1.25. So every cost report and quota estimate for the old defaults understated spend by roughly 2–4x, depending on tier and on the input/output token mix. That matters for the $50 beta budget in D004.
3. **gpt-6-luna has a different wire default.** gpt-6-luna defaults to `reasoning_effort: medium`, while `gpt-5.4-mini`/`-nano` default to `none` (<https://developers.openai.com/api/docs/models/gpt-6-luna>, <https://developers.openai.com/api/docs/guides/latest-model>). With reasoning on, Chat Completions rejects `temperature` and function calling. Every performer depends on both: tool calls go through `cast/base_performer_class.py`, and temperature is set per role and pinned for benchmarks by ADR-0003. The GPT-5.4 family already defaults to no reasoning, so this constraint never came up before.

The benchmark gate adds a fourth constraint. The pinned baselines under `benchmarks/baselines/` and the tracked noise floor in `benchmarks/baselines/.calibration.json` were all recorded on the GPT-5.4 engine. Each file's `engine_models` block shows `director_model/narrator_model: gpt-5.4-mini`, `agent_model/dramaturge_model: gpt-5.4-nano`. ADR-0002 notes that auto-compare assumes the same engine model set on both sides and does not check `engine_models` for mismatches.

## Decision

1. **Role defaults.** `Config.director_model`, `agent_model`, `narrator_model`, and `dramaturge_model` all default to `gpt-6-luna` (`config.py`). `AI_MODELS.gpt6_luna` is registered in `defaults/models.py`; `OpenAIClient`'s constructor default and `GameEngine()`'s direct-construction role defaults (`engine/game_engine.py`) are `gpt-6-luna` too. The per-role `*_MODEL` env vars and admin role overrides still take precedence.
2. **Reasoning pinned off.** `OpenAIClient._build_request_kwargs` sends `reasoning_effort: "none"` when the model id starts with a prefix in `_REASONING_NONE_MODEL_PREFIXES` (currently only `"gpt-6-luna"`). Other models get no `reasoning_effort` field, so their wire payload does not change.
3. **Benchmark engine pins stay on GPT-5.4.** Every workflow that produces or consumes pinned baselines or the tracked noise floor keeps all four engine role models (including `DRAMATURGE_MODEL`, so recorded `engine_models` metadata matches the baselines) pinned to the set recorded in the baselines' `engine_models`, until `main` is re-pinned per ADR-0002. That covers `benchmark-on-pr.yml`, `benchmark-baseline.yml`, `benchmark.yml`, and `noise-floor-recalibration.yml`. The e2e job in `ci.yml` does not score against baselines, so it moves to `gpt-6-luna` to exercise the production default.
4. **Judge panel unchanged.** `benchmarks/harness/panel.py`'s `DEFAULT_ROSTER` keeps its six witnesses: opus, sonnet, haiku, gpt-5.4, gpt-5.4-mini, gpt-5.4-nano. The CI cap stays at an odd 5 (ADR-0013). Judges reference `AI_MODELS.gpt5_4*` directly, not the role defaults, so this change does not move them. (ADR-0019 later refreshed the roster to current models.)
5. **Pricing corrected.** `DEFAULT_MODEL_PRICES` adds `gpt-6-luna` at $0.10 / $0.50 and corrects `gpt-5.4-mini` to $0.75 / $4.50 and `gpt-5.4-nano` to $0.20 / $1.25 (USD per 1M tokens, standard tier). `MODEL_PRICING_JSON` overrides still win.

## Rationale

- **Cost.** With corrected prices, gpt-6-luna is cheaper than the old defaults on every axis. Against `gpt-5.4-mini` (Director, Narrator) it is 7.5x cheaper on input and 9x on output. Against `gpt-5.4-nano` (supporting agents) it is 2x on input and 2.5x on output. For a beta capped by D004's $50 budget, the default model sets how many sessions testers get.
- **One default instead of a split.** A single model for all roles removes the mini/nano tiering from defaults. Per-role env vars keep the split available to anyone who wants it.
- **Pinning reasoning off keeps the GPT-5.4 wire contract.** Every performer already relies on Chat Completions function calling and an explicit temperature. ADR-0003's benchmark determinism depends on the API accepting `temperature`. Pinning `none` keeps both working without touching any performer. *Inferred, not measured:* it also avoids paying for hidden reasoning tokens (billed as output) and their latency on every turn.
- **Benchmarks stay on the model their baselines describe.** Scoring a gpt-6-luna engine against GPT-5.4 baselines would report the model swap as a regression or improvement, and would read it as noise-floor drift in the monthly recalibration. This is the exact failure ADR-0002 warns about. The honest move is to keep scoring like against like until the paid, human-gated re-pin is done.
- **The judge panel is a separate instrument.** ADR-0013's noise floor is calibrated on that exact panel. Changing judges together with the engine would confound two variables in one re-pin.

**Open question: quality.** No benchmark or golden-snapshot evidence in the repo compares gpt-6-luna prose or orchestration against the GPT-5.4 split. This decision rests on cost and wire compatibility. Narrative quality on the new default is unmeasured until the re-pin below runs.

## Alternatives considered

### Alternative 1: Keep the GPT-5.4 mini/nano split

Would keep production on the model the benchmarks measure. Not chosen: on corrected prices the split costs several times more per token for no measured quality benefit. It stays one env-var change away for any deployment that wants it.

### Alternative 2: Let gpt-6-luna use its API-default reasoning

Would use the model's reasoning mode. Rejected: with reasoning on, Chat Completions rejects `temperature` and function calling. That would break every tool-calling performer and ADR-0003's temperature pin.

### Alternative 3: Migrate `OpenAIClient` to the Responses API so reasoning and tools can coexist

Would unlock reasoning for performers. Not chosen now (*Inferred*): it is a wire-contract migration across every performer and the call logger, far larger than a default swap. Nothing yet shows performers need reasoning.

### Alternative 4: Make `reasoning_effort` a per-`ModelConfig` field

More configurable. Not chosen (*Inferred*): one model needs the pin today, and a prefix tuple next to the client is the smallest change that the wire-level tests can verify. Revisit if a second family needs a different effort level.

### Alternative 5: Move the benchmark workflow pins to gpt-6-luna in the same change

Would make benchmarks measure the production default right away. Rejected: the pinned baselines and `.calibration.json` describe the GPT-5.4 engine. Every PR comment would compare across models, and the monthly recalibration would flag the swap as ≥50% stdev drift. The workflows move only together with re-pinned baselines (see Follow-up).

### Alternative 6: Add gpt-6-luna to the judge panel

Not chosen: ADR-0013 fixes the panel and its odd cap. The noise floor is scaled to that panel. Judge composition is a separate decision from engine defaults.

## Consequences

Positive consequences:
- Lower per-token cost on every role at the default configuration.
- Cost reports and quota estimates use corrected rates, so D004 budget reviews see realistic spend.
- The e2e CI job now exercises the production default model.
- Payloads to non-luna models are unchanged; the `reasoning_effort` field is sent only when needed.

Tradeoffs / risks:
- **Production and benchmarks now run different models.** Players get gpt-6-luna; PR benchmark comments still score GPT-5.4. A prompt change that helps on GPT-5.4 but hurts on gpt-6-luna will not show up in the benchmark gate until the re-pin.
- **Historical cost reports re-price when read.** `costs/reports.py` prices `ai_call_logs` rows at report time, so past GPT-5.4 usage now reports 2–4x higher than before (the mini-priced test fixture total moved from $1.25 to $3.00). Compare D004 budget reviews across this change with that in mind.
- **The reasoning pin is a model-id prefix match.** Any future model id starting with `gpt-6-luna` inherits `reasoning_effort: none`. Another reasoning-by-default model does not get it and will fail on `temperature` and tool calls until it is added to the tuple. Routing gpt-6-luna through OpenRouter (`openai/gpt-6-luna`) does not match the prefix, so the pin is not sent there.
- **The ratchet stamps the baseline's old `engine_models`.** `_ratchet_one` in `benchmarks/cli/_run_compare.py` copies `baseline.engine_models` into the refreshed baseline. Running `--update-baselines-on-improvement` with a gpt-6-luna engine would write luna scores labelled as GPT-5.4.
- **`noise-floor-recalibration.yml` does not parse on `main` (predates this ADR).** The multi-line `gh issue create --body` string in its `run: |` block starts at column 1, so GitHub rejects the workflow and the monthly recalibration does not run. This change adds the GPT-5.4 pin so the workflow is correct once the YAML is fixed.
- **Luna exposed a Director routing-context gap.** On the first live e2e run (2 of 2 attempts), gpt-6-luna's Director did not route "Ask the forum guard…" to the guard's Actor. The Director's NPC list showed only `- Marcus`. The NPC's occupation never reached the prompt, so role references like "the guard" had nothing to match against; gpt-5.4-mini had been guessing. The fix, owner-approved in favour of keeping the Director on Luna, has three parts. `format_npcs_present` now renders `- name, occupation (status) — appearance`. The Director rules (EN and RU) match role or occupation references the same way they match visible features. `DirectorRouter.route_action` logs the chosen tool, so live routing failures can be diagnosed.
- **Snapshot ids are priced as their base model.** `_record_llm_call` logs `response.model`, which OpenAI returns as a dated snapshot id (e.g. `gpt-5.4-nano-2026-03-17`). `price_for_model` tries the exact id first, so a `MODEL_PRICING_JSON` entry for a snapshot still wins, then falls back to the id with its `-YYYY-MM-DD` suffix stripped. Without that fallback, production Luna calls would be flagged `unpriced` and left out of the D004 budget.

What future agents must preserve:
- **Never switch the engine model on a benchmark scoring path without re-pinning.** `benchmark-on-pr.yml`, `benchmark-baseline.yml`, `benchmark.yml`, and `noise-floor-recalibration.yml` must pin the same engine role models as the `engine_models` block in `benchmarks/baselines/*.json` and `.calibration.json`. A workflow with no `*_MODEL` env silently follows `config.py` defaults, which is now a different model. Flip all four together, in the same PR that commits re-pinned baselines.
- **Do not ratchet across a model switch.** Move baselines onto a new engine with `benchmarks calibrate` plus `benchmarks pin` from a fresh aggregate, which carries its own `engine_models`. Never use `--update-baselines-on-improvement` for this.
- **Keep `reasoning_effort: none` for gpt-6-luna while performers use Chat Completions with tools and temperature.** Removing it breaks every tool-calling performer and ADR-0003. Before adding a model to `_REASONING_NONE_MODEL_PREFIXES`, confirm it accepts `none`.
- **Only reasoning-default models get the field.** Do not send `reasoning_effort` to models that don't take it; `test_other_models_omit_reasoning_effort` guards this.
- **The judge panel does not follow engine defaults.** Change `DEFAULT_ROSTER` only through an ADR-0013 supersession that also recalibrates the noise floor.
- **The price table records the provider's published standard rates.** Update it when the provider changes prices. Deployment-specific rates go in `MODEL_PRICING_JSON`, not in the checked-in defaults.

## Follow-up: moving benchmarks onto gpt-6-luna

This is a paid, human-gated step. It never runs on CI (ADR-0002).

1. Run `benchmarks calibrate` with the gpt-6-luna engine, `BENCHMARK_TEMPERATURE_OVERRIDE=0.0` (ADR-0003), the seeded dice (ADR-0015), and `--max-judges 5` (ADR-0013).
2. Run `benchmarks pin <scenario>` from each fresh aggregate so the baselines carry `engine_models` for gpt-6-luna and the new noise floor.
3. In the same PR, change the engine pins (all four roles) in all four scoring workflows to `gpt-6-luna`.
4. Update this ADR's status or supersede it. The "benchmark pins stay on GPT-5.4" clause ends there.

## Verification / tests

- `tests/test_config.py::TestDefaultsExports::test_role_models_default_to_gpt6_luna`: all four role fields default to `gpt-6-luna`.
- `tests/test_config.py::TestDefaultsExports::test_ai_models_gpt6_luna`: registry entry.
- `tests/test_game_engine.py::test_default_role_models_match_config_defaults`: `GameEngine()` direct-construction defaults match `Config`'s.
- `tests/test_openai_reasoning_effort.py`:
  - `test_gpt6_luna_pins_reasoning_effort_none`: a luna tool-call request carries `reasoning_effort: none` next to `temperature` and `tool_choice`.
  - `test_other_models_omit_reasoning_effort`: GPT-5.4, GPT-4, and DeepSeek payloads have no such field.
  - `test_default_role_model_pins_reasoning_none_on_wire`: consumer-side seam; each role default, resolved through `resolve_model_config` and `create_llm_client`, reaches the SDK call with the pin.
- `tests/test_model_pricing.py::test_checked_in_openai_prices_match_published_rates` and `test_known_model_cost_uses_decimal_prices`: corrected table and luna pricing.
- `tests/test_admin_cost_reports.py`: admin cost summary totals re-priced.
- Review check: `grep -n "_MODEL:" .github/workflows/benchmark*.yml .github/workflows/noise-floor-recalibration.yml` shows the GPT-5.4 set in every scoring workflow and matches `engine_models` in `benchmarks/baselines/*.json`. `ci.yml`'s e2e job shows `gpt-6-luna`.

## Related files

- `config.py`
- `defaults/models.py`
- `engine/game_engine.py`
- `llm/openai_client.py`
- `costs/model_pricing.py`
- `benchmarks/harness/panel.py`
- `benchmarks/cli/_run_compare.py`
- `benchmarks/baselines/*.json`, `benchmarks/baselines/.calibration.json`
- `.github/workflows/benchmark-on-pr.yml`, `.github/workflows/benchmark-baseline.yml`, `.github/workflows/benchmark.yml`, `.github/workflows/noise-floor-recalibration.yml`, `.github/workflows/ci.yml`
- `.env.example`, `README.md`, `CLAUDE.md`
- `tests/test_config.py`, `tests/test_game_engine.py`, `tests/test_openai_reasoning_effort.py`, `tests/test_model_pricing.py`, `tests/test_admin_cost_reports.py`
