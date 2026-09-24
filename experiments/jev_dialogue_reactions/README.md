# Jev for NPC understanding and dialogue reactions

Status: predeclared pilot design, 2026-09-24. This experiment changes no runtime behavior.

## Question

Does a Jev judgment about what the NPC understands and how they immediately react improve the actual Actor's spoken reply? Compare it with both the unmodified Actor and the same Actor given a generic reminder to respect its knowledge and distinguish surprise from fear. The reminder arm controls for the effect of adding more prompt text without a Jev decision.

## Design

`cases.json` fixes eight fictional situations before live calls. Six are in English and two in Russian. They cover an unfamiliar word alone, a visible inexplicable voice and light, the same object after an NPC has witnessed it and heard the player's explanation, a role contrast (guard versus scholar), unfamiliar medicine, and a modern-radio negative control. The previously taught cases are seeded as `PERSONAL_EXPERIENCE` with a `WITNESSED` edge and player `subject_id`, so the real Actor memory selector receives them. Every arm starts from fresh state and uses the same NPC facts, scene, player utterance, Actor model, and dialogue envelope.

The three Actor arms are:

1. **Baseline** — the current Actor prompt and player input.
2. **Reminder** — baseline plus a generic instruction to check knowledge, avoid treating a player's claim as proof, and distinguish surprise from danger.
3. **Jev-guided** — reminder plus Jev's two typed choices: `understanding` (`known`, `partial`, `unknown`) and an immediate outward expression (`ordinary`, `curious`, `startled`, `wary`, `afraid`, `skeptical`). This cue is explicitly fallible, is not a world fact, and does not update `current_mood`.

Jev `jev-1.13.0` receives only NPC-visible case information. It evaluates both questions in one System One request. Actor uses `gpt-5.4-nano`. Three independent repetitions per case are planned. This is an exploratory sample, not a statistically powered estimate.

## Predeclared rubric

Each case in `cases.json` states acceptable Jev labels and an output rubric. Review the Actor's spoken text for these errors:

- **Knowledge leak:** NPC asserts an unlearned modern mechanism or treats a player's unverified explanation as established fact.
- **Memory miss:** after the prior encounter, NPC responds as if the object is entirely new or forgets the witnessed observation and explanation.
- **Reaction mismatch:** fear without a credible threat, no acknowledgment of an uncanny observed event, or awe at a familiar modern radio.
- **Voice/agency mismatch:** NPC merely repeats a label or a generic line instead of reacting in their role and speech style.

An unfamiliar word does not itself imply danger. Absence from the knowledge graph does not prove ignorance of every ordinary fact. `partial` includes a reasonable inference or a remembered claim without knowing its truth or mechanism. The Russian cases are reviewed separately because TypeSafe documents English as its strongest language. Review Jev's choice against the case expectations, then compare all three Actor outputs without treating Jev as ground truth. Report raw counts and examples, including regressions, rather than only an average quality score.

This pilot does not let Jev write speech, change emotional-memory values, choose contested outcomes, or update relationships. ADR-0011 keeps those emotional values and drift deterministic. The Actor's `mood` output and resulting NPC mood are recorded to catch accidental use of `terrified` or other labels outside the supported mechanical ladder.

## Reproduce

Dry run makes no provider calls. Live mode requires `TYPESAFE_API_KEY` and `OPENAI_API_KEY` in the process environment, and writes results to `/private/tmp/storyteller-jev-dialogue-results` by default.

```bash
PYTHONPATH=. uv run python experiments/jev_dialogue_reactions/run.py
PYTHONPATH=. uv run python experiments/jev_dialogue_reactions/run.py --live
```
