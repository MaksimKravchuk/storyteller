---
type: Decision
title: "Refresh the benchmark judge panel to current models"
status: stable
governs:
  - benchmarks/harness/panel.py
  - defaults/models.py
  - benchmarks/harness/judge.py
  - benchmarks/baselines/*.json
  - benchmarks/model_sets/smoke.py
  - tests/test_benchmarks_panel.py
  - tests/test_openai_reasoning_effort.py
  - tests/test_anthropic_reasoning_models.py
  - tests/test_benchmarks_judge_reasoning.py
  - .github/workflows/noise-floor-recalibration.yml
  - llm/openai_client.py
  - llm/anthropic_client.py
  - .github/workflows/benchmark-on-pr.yml
  - .github/workflows/benchmark-baseline.yml
  - benchmarks/baselines/.calibration.json
---
# ADR-0019: Refresh the benchmark judge panel to current models

Date: 2026-09-30
Status: Accepted
Decision owner: Max (approved the full roster refresh and the paid recalibration right after merge)
Related: ADR-0002 (pinned baselines, noise floor, ratchet), ADR-0003 (temperature pinning), ADR-0013 (judge panel, odd cap, Bayesian layer; this ADR supersedes its roster composition only), ADR-0015 (seeded dice), ADR-0018 (gpt-6-luna engine default, `reasoning_effort: none` pin)

## Context

ADR-0013 fixed `DEFAULT_ROSTER` in `benchmarks/harness/panel.py` at six witnesses: three Anthropic (`claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`), then three OpenAI (`gpt-5.4`, `gpt-5.4-mini`, `gpt-5.4-nano`). CI caps the panel at an odd 5, so the first five vote. ADR-0018 moved the engine to `gpt-6-luna` and left the judges alone on purpose. It also set a guardrail: change `DEFAULT_ROSTER` only through an ADR-0013 supersession that also recalibrates the noise floor. This ADR is that supersession.

Both providers have moved on a generation. ADR-0018 records that GPT-5.4 is no longer in OpenAI's flagship list. The current lineup is GPT-6 Astra, GPT-6.1 Sol and GPT-6 Luna. On the Anthropic side, Opus 4.6 and Sonnet 4.6 have been succeeded by Opus 5.5 and Sonnet 5.5.

The new models do not accept the request the judge path used to send. `run_judge` calls every judge with `temperature=0` and `max_tokens=400`, and the clients passed `temperature` through unconditionally. This change was built against these provider constraints:

- **`gpt-6-astra` and `gpt-6.1-sol`** reject `reasoning_effort: none`. With reasoning on, they reject `temperature`.
- **`claude-opus-5-5` and `claude-sonnet-5-5`** always think and reject `temperature`.
- **Thinking and reasoning tokens use the output budget.** A 400-token cap can be used up before the verdict JSON is written. The body comes back empty or truncated, fails to parse on both the first try and the retry, and becomes an ERROR vote.
- **`gpt-6-luna`** accepts `reasoning_effort: none` plus `temperature` (ADR-0018). **`claude-haiku-4-5`** accepts `temperature`.

The recalibration that must follow a panel change could not run. `noise-floor-recalibration.yml` on `main` is invalid YAML (ADR-0018 records this). Its multi-line `gh issue create --body` string starts lines at column 1 inside a `run: |` block, and `yaml.safe_load` fails at line 58. Its artifact step also uploaded `.calibration.json` only when `exit_code == '0'`. A deliberate panel change is expected to exit 1 on drift, so the new noise floor was never archived.

**Reported finding (not re-verified in this record):** the `ANTHROPIC_API_KEY` repository secret is empty in CI. `assemble_panel` skips every Anthropic candidate with `no anthropic api key`, so CI panels today contain only OpenAI judges.

## Decision

1. **Roster.** `DEFAULT_ROSTER` keeps its order (three Anthropic, then three OpenAI) and its six slots:

   | Slot | Alias | Model id |
   |---|---|---|
   | 1 | `opus` | `claude-opus-5-5` |
   | 2 | `sonnet` | `claude-sonnet-5-5` |
   | 3 | `haiku` | `claude-haiku-4-5` |
   | 4 | `gpt-6-astra` | `gpt-6-astra` |
   | 5 | `gpt-6.1-sol` | `gpt-6.1-sol` |
   | 6 | `gpt-6-luna` | `gpt-6-luna` |

   The Claude entries are updated in place in `AI_MODELS` (`defaults/models.py`). `gpt6_astra` and `gpt6_1_sol` are added. The `gpt5_4*` entries stay because non-judge code still uses them (smoke probes, tests).
2. **Cap unchanged (ADR-0013).** `DEFAULT_MAX_JUDGES = 6` for ad-hoc runs. `--max-judges 5` stays in `benchmark-on-pr.yml`, `benchmark-baseline.yml` and `noise-floor-recalibration.yml`. When both keys are present, the five judges are opus, sonnet, haiku, astra and sol. Luna is sixth, so it votes only in full-roster runs or when a key is missing.
3. **Wire rules**, matched by model-id prefix in the clients:

   | Model | Client | Sent | Omitted |
   |---|---|---|---|
   | `gpt-6-astra`, `gpt-6.1-sol` | `OpenAIClient` (`_REASONING_LOW_MODEL_PREFIXES`) | `reasoning_effort: "low"` | `temperature` |
   | `gpt-6-luna` | `OpenAIClient` (`_REASONING_NONE_MODEL_PREFIXES`) | `reasoning_effort: "none"` + `temperature` (unchanged from ADR-0018) | — |
   | `claude-opus-5-5`, `claude-sonnet-5-5` | `AnthropicClient` (`_ALWAYS_THINKING_MODEL_PREFIXES`) | `output_config: {"effort": "low"}` | `temperature` |
   | `claude-haiku-4-5`, every other model | both | `temperature` as before | effort fields |

   These rules apply to every caller of those model ids, not only to judges.
4. **Judge token cap.** `_JUDGE_MAX_TOKENS` rises from 400 to 4096 (`benchmarks/harness/judge.py`) so thinking tokens do not truncate the verdict. `_JUDGE_TEMPERATURE` stays 0, but only Haiku and Luna receive it on the wire.
5. **No provider-side fallbacks on judge calls.** Judge requests do not turn on any server-side refusal or failure fallback that routes the call to a different model. A failed judge stays an ERROR vote (existing `_error_vote` path) and lowers the live vote count.
6. **Recalibration workflow fixed.** `noise-floor-recalibration.yml` builds the drift-issue body in a file and passes `--body-file`. The `.calibration.json` artifact now uploads whenever calibration ran (`always() && steps.calibrate.outputs.exit_code != ''`), including on drift.
7. **Engine pins are not touched here.** The four scoring workflows keep the GPT-5.4 engine pins from ADR-0018. Phase 2 (owner-approved, see Follow-up) recalibrates and re-pins with the new panel and the Luna engine, and flips the engine pins in the same PR.

## Rationale

- **The panel should measure with current models.** Max approved a full refresh rather than a partial swap.
- **Order and odd cap preserve ADR-0013's guarantees.** With both keys the CI panel is still three Anthropic plus two OpenAI judges, and still odd. That avoids the 3–3 `round(0.5) == 0` downward bias on 1-point elements.
- **`low` effort is the nearest valid request to the old one.** The judge prompt is a short yes/no question with a verbatim quote, written for models that did not reason. `none` is rejected by astra and sol, and thinking cannot be turned off on Opus 5.5 or Sonnet 5.5. `low` is the smallest valid setting. *Inferred, not measured:* it also keeps reasoning-token cost and latency as low as the models allow.
- **Temperature must be omitted, not zeroed.** These models reject the field, so sending `temperature=0` fails the whole request. Omitting it is the only way to get a vote.
- **Prefix tuples in the client, revisiting ADR-0018 Alternative 4.** ADR-0018 said to revisit a per-`ModelConfig` reasoning field "if a second family needs a different effort level". That condition is now met, and prefix tuples are still the choice. Whether a model accepts `temperature` or `none` is fixed by its provider. Keying the rule to the model id means no configuration can build a request the API will reject. A per-config field would allow those combinations. Each tuple is also covered by a wire-level test.
- **4096 is a ceiling, not a spend.** Output tokens are billed as used, so the cap costs nothing when a judge answers briefly. It only stops a reasoning judge being cut off before its verdict.
- **Fallbacks would corrupt attribution.** A vote is recorded under `PanelMember.model_id`. If a provider silently answered with another model, the panel would count that model's vote as the member's. Per-judge tallies (`k_yes`/`n_votes`, ADR-0013) and any per-judge error rates would then describe a model that did not vote. An honest ERROR vote is better than a mislabelled YES/NO.
- **Recalibration is mandatory.** ADR-0002 and ADR-0013 scale every verdict by the calibrated `noise_floor_stdev`. New judges, now without temperature 0, are a different instrument. The workflow that measures it has to parse and has to keep its output when it detects drift.

**Owner override of ADR-0018's confound argument.** ADR-0018 kept the judges fixed partly because changing judges and the engine in one re-pin "would confound two variables". Phase 2 does exactly that, and Max approved it. A re-pin sets a new reference rather than comparing against the old one. The cost is that the repo will not have a separate measurement of how gpt-6-luna prose compares with GPT-5.4 prose on a fixed panel. ADR-0018's quality open question stays open.

## Alternatives considered

### Alternative 1: Keep the ADR-0013 roster

This would keep the calibrated instrument intact and temperature-0 deterministic. Not chosen: the panel would keep judging with a previous model generation on both providers, and Max chose a full refresh.

### Alternative 2: Refresh only models that accept `temperature=0`

This would keep judge determinism. Not chosen: on the current lineups only `gpt-6-luna` and `claude-haiku-4-5` accept temperature, which is too few for a five-judge panel across both providers. Max approved the full refresh knowing it costs determinism.

### Alternative 3: Default or higher reasoning effort for judges

This might give more careful verdicts. Not chosen (*Inferred*): there is no evidence that the yes/no quote task needs it. Higher effort costs more tokens and time and pushes harder on the token cap.

### Alternative 4: A per-`ModelConfig` `reasoning_effort` / `effort` field

This would be more configurable. Not chosen: see Rationale. Provider constraints are properties of the model id, and a config field would let callers build requests that fail.

### Alternative 5: Turn on provider-side fallbacks so a refused judge still votes

This would give fewer ERROR votes. Rejected: the vote would be attributed to the wrong model (see Rationale).

### Alternative 6: Recalibrate and re-pin in this same PR

This would avoid a window where old baselines are scored with new judges. Not chosen: recalibration is paid and human-gated, and it never runs on CI (ADR-0002). The owner-approved phase 2 also includes the engine flip, which ADR-0018 requires to land in the same PR as the re-pinned baselines.

## Consequences

Positive consequences:
- The panel uses the current model generation from both providers.
- Reasoning judges get requests their APIs accept, with room to think before the verdict.
- The monthly recalibration workflow parses again and keeps the new noise floor when drift is detected.

Tradeoffs / risks:
- **Judges are no longer deterministic at temperature 0.** Four of six judges (astra, sol, opus, sonnet) run without `temperature`. In the CI five with both keys, only Haiku gets temperature 0. Judge variance, which ADR-0013 names as the dominant residual noise, is expected to rise. The noise floor has to be recalibrated (ADR-0002 / ADR-0013), and the ratchet's `2 * noise_floor_stdev` bar will likely widen.
- **Mismatch window until phase 2.** Until the re-pin, PR comments score new-panel results against baselines and a noise floor from the old panel. Judges can pass or fail elements at different rates, so deltas may read as regressions or improvements with no engine change, and Bayesian probabilities are scaled by the wrong stdev. Baselines record `engine_models` but not the judge panel (`benchmarks/baselines/*.json`), so nothing detects this automatically.
- **CI panel depends on which keys exist.** With the Anthropic secret empty, the CI panel is astra, sol and luna: three live judges, odd, so no tie bias. Adding the secret changes it to opus, sonnet, haiku, astra and sol, which is a different instrument, so a noise floor calibrated on the OpenAI-only panel stops applying. A judge ERROR on a three-judge panel leaves two votes, which can tie (ADR-0013 caveat).
- **Luna can judge Luna.** While the Anthropic key is missing, `gpt-6-luna` is on the CI panel. After phase 2 it is also the engine, so it would judge its own prose. *Open question:* whether self-preference moves scores here has not been measured. With both keys, Luna falls outside the cap.
- **Per-PR judge cost is unmeasured.** Reasoning tokens are billed as output. ADR-0013's ~$0.04–$0.20 per-PR estimate predates this panel. *Open question:* re-measure after phase 2.
- **Prefix matching has the same edges as ADR-0018.** Dated snapshots of these ids inherit their rule. OpenRouter-routed ids (`anthropic/claude-opus-5-5`, `openai/gpt-6-astra`) do not match and will fail on `temperature`. Any future always-thinking or reasoning-only model fails until someone adds it to the right tuple.
- **The wire rules reach beyond judges.** Setting a role to `claude-opus-5-5`, `claude-sonnet-5-5`, `gpt-6-astra` or `gpt-6.1-sol` (for example `NARRATOR_MODEL`) drops that performer's temperature. ADR-0003's benchmark temperature pin cannot make that engine deterministic.
- **Shared registry entries moved.** `AI_MODELS.claude_opus`, `claude_sonnet` and `claude_haiku` now point at the new ids for every consumer. That includes the `max-narrator` probe in `benchmarks/model_sets/smoke.py`.

What future agents must preserve:
- **ADR-0013's panel rules still hold.** Keep the three-Anthropic-then-three-OpenAI order and an odd cap of 5, identical across `benchmark-on-pr.yml`, `benchmark-baseline.yml` and `noise-floor-recalibration.yml`.
- **Any change to who votes is a new instrument.** That covers editing `DEFAULT_ROSTER`, the cap, or which provider keys CI has. It needs a recalibration and re-pin (ADR-0002), and a roster change also needs a record that supersedes this one.
- **Calibrate on the panel CI actually fields.** Before pinning, check the "Skipped panel candidates" section of the calibration reports. It must match what PR runs skip.
- **Keep the wire rules.** Never send `temperature` to astra, sol, Opus 5.5 or Sonnet 5.5. Never send `reasoning_effort` or `output_config` to models that do not take them (`test_other_models_omit_reasoning_effort`, `test_haiku_keeps_temperature`). Luna stays on `none` plus `temperature` (ADR-0018).
- **Keep `_JUDGE_MAX_TOKENS` large enough for thinking.** The consumer-seam tests assert at least 4096.
- **No provider-side fallbacks on judge calls.** A failed judge is an ERROR vote under its own `model_id`, never a vote from another model.
- **Do not claim temperature-0 judge determinism.** It now holds only for Haiku and Luna.
- **Keep the recalibration workflow valid.** Use `--body-file`, not a multi-line `--body`, inside a `run: |` block. Keep the `.calibration.json` upload running on drift.

## Follow-up: phase 2 recalibration and re-pin (owner-approved)

This is paid and human-gated. It never runs on CI (ADR-0002).

1. Decide which panel to calibrate on. The preferred path is to add the `ANTHROPIC_API_KEY` secret first, so calibration and PR runs both use opus, sonnet, haiku, astra and sol. If the calibration uses a different key set than CI, it will not match the PR runs.
2. Run `benchmarks calibrate --iterations 5 --max-judges 5` with the gpt-6-luna engine, `BENCHMARK_TEMPERATURE_OVERRIDE=0.0` (ADR-0003) and the seeded dice (ADR-0015).
3. Run `benchmarks pin <scenario>` from each fresh aggregate. Never re-pin with `--update-baselines-on-improvement` (ADR-0018).
4. In the same PR, flip all four engine role pins in the four scoring workflows to `gpt-6-luna`, per ADR-0018's follow-up, and update ADR-0018's "benchmark pins stay on GPT-5.4" clause.
5. Update this ADR: mark the mismatch window closed and record the measured per-PR judge cost.

## Verification / tests

- `tests/test_benchmarks_panel.py`:
  - `test_default_roster_uses_current_models` pins the six model ids in order.
  - `test_resolve_roster_with_overrides_preserves_order` and `test_overrides_still_key_filtered` cover the new OpenAI aliases.
- `tests/test_openai_reasoning_effort.py`:
  - `test_reasoning_only_models_send_low_effort_without_temperature` (astra, sol): `reasoning_effort: low`, no `temperature`.
  - `test_gpt6_luna_pins_reasoning_effort_none` and `test_other_models_omit_reasoning_effort` (ADR-0018 guards, unchanged).
- `tests/test_anthropic_reasoning_models.py`:
  - `test_reasoning_models_drop_temperature_and_pin_low_effort` (Opus 5.5, Sonnet 5.5).
  - `test_haiku_keeps_temperature`: Haiku keeps temperature and gets no effort field.
- `tests/test_benchmarks_judge_reasoning.py`, a consumer-seam test: `_send_judge_prompt` for `gpt-6.1-sol` and `claude-opus-5-5` reaches the SDK with low effort, no `temperature`, and a token cap of at least 4096.
- Workflow review check: `yaml.safe_load` parses `.github/workflows/noise-floor-recalibration.yml` (the `main` version fails at line 58). The archive step's `if:` runs on drift.
- Run review check: each benchmark report's "Skipped panel candidates" section shows who voted. With both keys, only `gpt-6-luna` should be skipped (panel cap). With the Anthropic key missing, all three Claude judges are skipped (`no anthropic api key`).

## Related files

- `defaults/models.py`
- `benchmarks/harness/panel.py`
- `benchmarks/harness/judge.py`
- `llm/openai_client.py`
- `llm/anthropic_client.py`
- `.github/workflows/noise-floor-recalibration.yml`
- `.github/workflows/benchmark-on-pr.yml`, `.github/workflows/benchmark-baseline.yml` (unchanged `--max-judges 5`)
- `benchmarks/baselines/*.json`, `benchmarks/baselines/.calibration.json` (re-pinned in phase 2)
- `benchmarks/model_sets/smoke.py` (shares `AI_MODELS.claude_sonnet`)
- `tests/test_benchmarks_panel.py`, `tests/test_openai_reasoning_effort.py`, `tests/test_anthropic_reasoning_models.py`, `tests/test_benchmarks_judge_reasoning.py`
- `docs/decisions/0013-bayesian-benchmark-comparison-layer.md`, `docs/decisions/0018-default-agent-roles-to-gpt-6-luna.md`
