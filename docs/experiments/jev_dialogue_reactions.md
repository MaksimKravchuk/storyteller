# Jev for NPC understanding and dialogue reactions

Status: complete exploratory pilot, 2026-09-24. This experiment changes no runtime behavior.

> The runner, cases and raw results (`experiments/jev_dialogue_reactions/`) were removed from the tree; they are in git history at commit `80cf94f`. The commands and file names below refer to that snapshot.

## Question

Does a Jev judgment about what the NPC understands and how they immediately react improve the actual Actor's spoken reply? Compare it with both the unmodified Actor and the same Actor given a generic reminder to respect its knowledge and distinguish surprise from fear. The reminder arm controls for the effect of adding more prompt text without a Jev decision.

## Design

`cases.json` fixes eight fictional situations before live calls. Six are in English and two in Russian. They cover an unfamiliar word alone, a visible inexplicable voice and light, the same object after an NPC has witnessed it and heard the player's explanation, a role contrast (guard versus scholar), unfamiliar medicine, and a modern-radio negative control. The previously taught cases are seeded as `PERSONAL_EXPERIENCE` with a `WITNESSED` edge and player `subject_id`, so the real Actor memory selector receives them. Every arm starts from fresh state and uses the same NPC facts, scene, player utterance, Actor model, and dialogue envelope.

The initial preregistration is commit `2990496`. Its first live run exposed a setup error: non-guard roles inherited the benchmark guard's name, appearance, and sword in the Actor prompt, while Jev did not see that equipment. Those outputs are diagnostic only and excluded from all comparative counts. Before the retained rerun, every case pinned identity, appearance, and inventory explicitly for both providers. The Jev cue also explicitly says it must not alone change `mood`, and the runner closes HTTP clients after each Actor call. The case situations and outcome rubric below are unchanged. The three diagnostic raw outputs are archived separately for audit.

The three Actor arms are:

1. **Baseline** — the current Actor prompt and player input.
2. **Reminder** — baseline plus a generic instruction to check knowledge, avoid treating a player's claim as proof, and distinguish surprise from danger.
3. **Jev-guided** — reminder plus Jev's two typed choices: `understanding` (`known`, `partial`, `unknown`) and an immediate outward expression (`ordinary`, `curious`, `startled`, `wary`, `afraid`, `skeptical`). This cue is explicitly fallible, is not a world fact, and does not update `current_mood`.

Jev `jev-1.13.0` receives only NPC-visible case information. It evaluates both questions in one System One request. Actor uses `gpt-5.4-nano`. Three independent repetitions per case were run. This is an exploratory sample, not a statistically powered estimate.

## Predeclared rubric

Each case in `cases.json` states acceptable Jev labels and an output rubric. Review the Actor's spoken text for these errors:

- **Knowledge leak:** NPC asserts an unlearned modern mechanism or treats a player's unverified explanation as established fact.
- **Memory miss:** after the prior encounter, NPC responds as if the object is entirely new or forgets the witnessed observation and explanation.
- **Reaction mismatch:** fear without a credible threat, no acknowledgment of an uncanny observed event, or awe at a familiar modern radio.
- **Voice/agency mismatch:** NPC merely repeats a label or a generic line instead of reacting in their role and speech style.

An unfamiliar word does not itself imply danger. Absence from the knowledge graph does not prove ignorance of every ordinary fact. `partial` includes a reasonable inference or a remembered claim without knowing its truth or mechanism. The Russian cases are reviewed separately because TypeSafe documents English as its strongest language. Review Jev's choice against the case expectations, then compare all three Actor outputs without treating Jev as ground truth. Report raw counts and examples, including regressions, rather than only an average quality score.

This pilot does not let Jev write speech, change emotional-memory values, choose contested outcomes, or update relationships. ADR-0011 keeps those emotional values and drift deterministic. The Actor's `mood` output and resulting NPC mood are recorded to catch accidental use of `terrified` or other labels outside the supported mechanical ladder.

## Retained live result

The retained raw outputs are `results_iter0.json`, `results_iter1.json`, and `results_iter2.json`: 8 cases × 3 repetitions, with one Jev decision and three fresh Actor runs per row (24 Jev and 72 Actor calls). All Actor envelopes parsed. Jev returned `jev-1.13.0` and Actor returned `gpt-5.4-nano-2026-03-17`. Jev's understanding choice fell within the predeclared acceptable labels in **24/24** rows, as did its expression choice in **24/24**. This checks the fixed cases, not general accuracy.

| Case | Jev understanding | Jev expression | Actor comparison across the three arms |
| --- | --- | --- | --- |
| Guard hears “smartphone” (EN) | unknown 3/3 | skeptical 3/3 | All ask for a familiar summons or an explanation; no fear or claimed technical knowledge. |
| Guard sees light and hears a voice (EN) | unknown 3/3 | startled 3/3 | All show caution without claiming to understand distant speech. |
| Guard sees the previously explained slab (EN) | partial 3/3 | wary 3/3 | All remember it. The unverified distance claim becomes an asserted fact in baseline 3/3, reminder 0/3, Jev-guided 2/3. |
| Scholar sees light and hears a voice (EN) | unknown 3/3 | curious 2/3, startled 1/3 | All investigate rather than panic; no clear Jev advantage in role-specific speech. |
| Healer hears “antibiotics” (EN) | unknown 3/3 | curious 3/3 | All decline the unavailable drug and offer era-appropriate care. |
| Modern guard hears “radio” (EN) | known 3/3 | ordinary 3/3 | All recognize a routine radio request. |
| Guard hears “смартфон” (RU) | unknown 3/3 | skeptical 3/3 | All ask for a familiar summons or explanation. |
| Guard sees the previously explained slab (RU) | partial 3/3 | wary 3/3 | All recall the light and voice without explaining the device. |

The most discriminating case is the guard's memory of a slab. The stored memory says the guard **witnessed** light and a stranger's voice, while the player **claimed** that the voice came from far away. A baseline line says “carried a voice from afar”; a Jev-guided line says “carried a voice from far off”. Both promote the claim to fact. The reminder instead says “by your word, carried voices from afar” or asks conditionally whether it is for distant speech. This is a narrow, manually adjudicated provenance error, not a score for all of dialogue quality. In the other seven cases, manual review found no clear knowledge, memory, or reaction violation that Jev consistently fixed. The Russian cases are only two prompts, so they are not evidence of broad Russian-language reliability.

All **72/72** retained Actor runs left the mechanical `mood` at `neutral`; transient caution, surprise, and curiosity appeared in speech rather than unsupported mood labels. The excluded diagnostic run had invalid mood labels in guided outputs. Because the protocol changed several prompt/context fields before the retained rerun, the difference cannot be attributed solely to the explicit mood safeguard.

Median elapsed time per call was **577 ms** for Jev, **1,154 ms** for baseline Actor, **1,242 ms** for reminder Actor, and **1,124 ms** for guided Actor. The median of Jev plus guided Actor elapsed time per row was **1,752 ms**; a serial integration would add the decision call to turn latency. Jev reported **21,540 input tokens** across 24 calls, about **$0.00090** at its [published input price](https://docs.typesafe.ai/models). Actor reported **86,837 prompt** and **6,569 completion tokens** across all 72 calls. These are provider-reported token counts; costs and latency can change with pricing and load.

The trial supports using Jev as a plausible *classification* signal for NPC perspective, but does not show that feeding those labels to Actor improves the spoken reply. In the one case that separates observation from an unverified claim, the generic reminder performed better than Jev guidance. A better next experiment would test a concise evidence/provenance cue at the Actor's memory-consumption seam, with more paraphrases and independent adjudication. It should preserve deterministic mood and relationship rules and should not assume that `unknown` in the knowledge graph means total ignorance.

## Reproduce

Dry run makes no provider calls. Live mode requires `TYPESAFE_API_KEY` and `OPENAI_API_KEY` in the process environment, and writes results to `storyteller-jev-dialogue-results/` in the system temp directory (`tempfile.gettempdir()`) by default.

```bash
PYTHONPATH=. uv run python experiments/jev_dialogue_reactions/run.py
PYTHONPATH=. uv run python experiments/jev_dialogue_reactions/run.py --live
```
