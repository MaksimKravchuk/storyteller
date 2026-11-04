# Jev and NPC reactions: controlled pilot

Status: complete exploratory pilot, 2026-09-24. Three live calls per case to Jev and to the existing Actor; game rules were not changed.

> The runner, cases and raw results (`experiments/jev_npc_reactions/`) were removed from the tree; they are in git history at commit `80cf94f`. The commands and file names below refer to that snapshot.

Validation: the six-case runner completed offline and live. Four automated tests cover the conditional dice baseline, Jev's request and response seam, and the actual `Actor.execute` prompt path. `ruff check`, `ruff format --check`, `flake8`, and `mypy` pass on the experiment and its tests. Human review of the 36 model answers below assesses plausibility; it is a small pilot, not a statistically powered quality estimate.

## Question

Would a context-aware decision model produce more plausible NPC reactions than the mood-only aggression check, and how would it compare with the existing Actor's autonomous action choice?

The compared units are different. `roll_aggression` only decides whether a retaliation attack is attempted, conditional on the Director offering that check. The Actor may already choose other context-aware actions in a separate phase. Jev's `choice` output would be a candidate decision for that phase; it cannot replace the combat or social success roll by itself.

## Fixed cases and rubric

All cases use fictional scene data. The first two deliberately hold the NPC, mood, and role constant while changing whether the player continues attacking or surrenders. The sixth repeats surrender in Russian. These cases are based on the repository's three-guard tavern benchmark; the merchant, bandit, and gate situation are controlled variations.

| Case | Mood | Player situation | Plausible immediate choices | Clear error |
| --- | --- | --- | --- | --- |
| guard_active_assault | angry | Still attacking another guard with a knife | restrain, attack, summon | wait or flee without helping |
| guard_surrender | angry | Dropped knife and raised hands | restrain, confront | attack to injure |
| merchant_threat | threatened | Armed player demands purse from unarmed merchant | withdraw, summon, confront | attack to injure |
| bandit_stolen_goods | angry | Player grabs armed bandit's bag and runs | attack, confront | wait without responding |
| guard_forged_permit | suspicious | Player presents dubious permit at quiet gate | confront, restrain | attack to injure |
| guard_surrender_ru | angry | Russian version of surrendered player | restrain, confront | attack to injure |

For Jev, send the same scene and NPC facts as structured `state` and ask one `choice` question with six options: `attack`, `restrain`, `confront`, `summon`, `withdraw`, `wait`. Record the chosen option, full distribution, confidence, latency, versioned model ID, and input tokens. Use `jev-1.13.0` to pin the model. For Actor, call the repository's `Actor.execute` in `is_npc_turn` mode with `_build_turn_prompt`, then retain raw JSON and elapsed time. Categorize its action from the text manually; record ambiguity rather than force a match. Three calls per case test short-run stability but do not establish reliability across scenes or models.

## Offline result

The current aggression check uses one d20 threshold per mood, independent of scene, biography, or player action. Conditional on that check being offered:

| Case | Attack probability |
| --- | ---: |
| guard_active_assault | 65% |
| guard_surrender | 65% |
| merchant_threat | 55% |
| bandit_stolen_goods | 65% |
| guard_forged_permit | 30% |
| guard_surrender_ru | 65% |

These numbers come from `AGGRESSION_THRESHOLDS` in `cast/dice.py`, not from sampled rolls. In particular, 65% is the conditional chance of an attack at `angry`; it is not the total chance of violence over the whole turn. The Director's eligibility gates and the Actor's actions still matter.

## Live result

The three raw outputs are `results_iter0.json`, `results_iter1.json`, and `results_iter2.json`. Jev returned `jev-1.13.0`; Actor's provider logs identified `gpt-5.4-nano-2026-03-17`. The Jev choice was stable across all three repeats for each case. The attack column is the mean of Jev's reported probability for the `attack` option, not a sampled game probability.

| Case | Jev choice (3/3) | Mean Jev P(attack) | Actor's described reaction (3/3) |
| --- | --- | ---: | --- |
| guard_active_assault | restrain | 28% | Blocks or pins the attacker's knife arm |
| guard_surrender | restrain | 0% | Disarms and secures the player |
| merchant_threat | summon | 0% | Backs away, calls for guards, or yields the purse |
| bandit_stolen_goods | attack | 87% | Pursues and attacks with a dagger |
| guard_forged_permit | confront | 0% | Inspects permit and challenges the player |
| guard_surrender_ru | restrain | 0.3% | Orders the player to keep hands visible, sometimes restraining |

Both methods avoided every predeclared clear error in these 18 decisions each. That assessment concerns the described action, not Actor's JSON `type`. The fixed six-choice menu gives Jev a narrower output space, and both systems saw the same fictional facts through different prompts. It is therefore evidence of context sensitivity, not proof that Jev improves the live game.

The Actor's structured `type` sometimes contradicted its own description. For the surrendered player it emitted `INTIMIDATE` once and `ATTACK` twice while describing disarming or arrest. For the merchant it emitted `MOVE` once for moving sideways within the scene, and `INTIMIDATE` twice for seeking help or yielding. In the Russian surrender case it emitted `MOVE` once while describing restraint. These labels matter: `cast/npc_turn.py` treats `ATTACK` and `INTIMIDATE` as contests, and `MOVE` removes the NPC from the scene. Jev's `restrain` answer names the intended action more cleanly, but `RESTRAIN` is not currently an engine action type.

Median per-call elapsed time was 597 ms for Jev and 1,790 ms for Actor across 18 paired calls. Jev returns only a decision; Actor returns action text. An implementation that also asks Actor to narrate after Jev would add Jev's latency to the turn. Jev reported 11,676 input tokens across all 18 calls; at the [documented $0.042 per million input tokens](https://docs.typesafe.ai/models), that is about **$0.00049**, with output tokens free. Actor token totals were logged by the provider but not retained in the raw JSON, so its total bill is not stated as a measured result. Its [published rates](https://developers.openai.com/api/docs/models/gpt-5.4-nano) are $0.20 per million input and $1.25 per million output tokens.

## Historical Actor evidence

The checked-in `benchmarks/baselines/autonomy_three_guards_tavern.json` records five runs at engine SHA `b3afacb2` (2026-06-22). Both bystanders produced a non-IDLE action in 5/5 runs, physical intervention passed in 5/5, and the mean scenario score was 9.8/10. Its witness panel voted yes 23/25 times on physical intervention. These are historical results for a punch in a tavern, not results from the six controlled cases above. They show why Jev's value must be judged against the existing Actor, especially on surrender and role-dependent reactions, rather than against the dice gate alone.

## Predeclared decision rule

Look first at the attack probability shift between `guard_active_assault` and `guard_surrender`. The dice cannot change here because the mood is identical. A useful Jev result should shift materially toward `restrain` or `confront` on surrender and avoid the clear errors above. Compare Jev with the existing Actor before concluding an extra API call improves the game. Inspect the Russian case separately. Record latency and token cost; do not infer Jev's decision quality from its confidence alone.

The repository's ADR-0011 keeps emotional values, mood, and relationship drift deterministic. This pilot concerns a proposed action choice only. Adopting Jev to produce any of those numbers would conflict with that decision and need a separate architecture decision.

## Interpretation

Jev recognized the same-mood active-assault versus surrender distinction that the aggression threshold cannot: attack probability fell from about 28% to zero, while `restrain` remained the top choice. Jev's reported confidence in `restrain` was only 0.33–0.44 during the active assault, versus 0.89–0.90 after surrender. Actor's prose already responded appropriately to that distinction, so the pilot does not show a narrative-quality gain from adding Jev. The most concrete problem revealed is disagreement between Actor's `action` and `type`, which can trigger the wrong game mechanic. Before changing runtime behavior, compare a constrained or validated Actor action schema against a Jev-guided action choice in a full-turn benchmark. Preserve dice for contested outcomes and the deterministic mood/relationship system.

## How to rerun

The fixed inputs are in `cases.json`, and the runner is `run.py`. Offline mode uses no API keys and writes `storyteller_jev_results.json` to the system temp directory (`tempfile.gettempdir()`). Live mode needs `TYPESAFE_API_KEY` and `OPENAI_API_KEY` in the process environment and makes six calls to each provider per iteration. The archived raw results contain fictional scene data and model outputs, with no credentials.

```bash
PYTHONPATH=. uv run python experiments/jev_npc_reactions/run.py
PYTHONPATH=. uv run python experiments/jev_npc_reactions/run.py --live
```

The repository quality gate passed: `ruff check`, `ruff format --check`, `flake8`, `mypy`, and 2,552 unit tests (excluding e2e and benchmarks). The unit tests required loopback access for the admin suite.
