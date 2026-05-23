# Storyteller Public Web Demo v0.1 release notes

Status: Draft for public demo launch. Do not publish until the release checklist and human approval gate are complete.

## What is Storyteller?

Storyteller is an AI-powered text quest engine for interactive fiction. You give it a historical, fictional, fantasy, or surreal setting; it researches and builds enough world context to start a playable scene, then runs a theater-style cast of AI agents behind the curtain:

- a Director coordinates the turn-by-turn story;
- setting and scene agents gather context, create locations, and keep the world grounded;
- NPC and narration agents turn that state into characters, dialogue, consequences, and prose;
- memory and timeline systems help the session remember recent events instead of treating every prompt as a fresh chat.

The result is meant to feel less like a blank chatbot and more like a short-form text adventure that can react to where you go, who you talk to, and what you try next.

## What is new in the public web demo?

The public web demo makes the core Storyteller loop available in a browser for the first time:

- **Start from your own premise.** Enter a setting or scenario prompt, such as medieval Novgorod, a lantern-keeper fantasy town, or a surreal office where Tuesdays can be filed and misplaced.
- **Play through the web UI.** The demo exposes the player-facing FastAPI web interface rather than requiring a local terminal setup.
- **Use natural-language actions.** Try common text-adventure moves like exploring, moving, inspecting, waiting, talking to NPCs, following clues, or taking a risky approach.
- **Meet generated characters and locations.** Storyteller creates NPCs, scene details, and immediate story hooks around the premise instead of asking you to pre-author a full campaign.
- **Test short-session continuity.** The demo is tuned for a short public play session where recent choices, names, clues, and consequences should carry forward across turns.
- **Evaluate the product direction.** This release is intentionally a feedback demo: it is designed to show what the multi-agent story engine can become and to surface the places where it still breaks down.

## Suggested things to try

If you want a quick sense of the demo, try one of these prompts:

```text
Start a grounded historical game in medieval Novgorod in the winter of 1185. I am a young scribe's apprentice sent to the market to recover a missing wax tablet before my master is blamed for a bad trade record.
```

```text
Start a fantasy game in Briarfall, a forest town where enchanted lanterns keep thorn-wraiths outside the palisade. I am a newly appointed lantern-keeper on my first night shift when one district suddenly goes dark.
```

```text
Start a surreal bureaucratic game in the Bureau of Misplaced Tuesdays. I am a temporary clerk whose desk drawer contains three copies of next Tuesday, one of which is growling and one of which has my signature on a resignation form I have never seen.
```

After the opening scene, try at least five turns: inspect something concrete, ask an NPC a specific question, move to a new location, make one unexpected choice, and see whether the story remembers what happened.

## Known limitations

This is a v0.1 public demo, not a finished game platform. Please expect rough edges:

- **Short sessions work best.** Long-running campaigns may lose detail, repeat themselves, or drift away from earlier facts.
- **Historical accuracy is not guaranteed.** Storyteller may produce plausible-sounding but incorrect details, anachronisms, or overconfident explanations.
- **NPC memory and motives are still developing.** Characters should often respond consistently, but they may forget names, clues, relationships, or prior choices.
- **The engine can still hallucinate or railroad.** Some turns may ignore part of your action, invent unsupported facts, or push too hard toward a predetermined outcome.
- **Unusual prompts are supported but not fully solved.** Surreal or edge-case scenarios are useful tests, but they can expose state-tracking and consistency problems.
- **Latency may vary.** Story setup and turn responses depend on LLM calls and can feel slow, especially for complex settings.
- **Safety and moderation are limited.** Do not treat the demo as a child-safe, fully moderated, or production-hardened environment.
- **No publishing or persistence guarantee.** Demo sessions may be reset, unavailable, or changed as the release candidate evolves.

## How to give feedback

Feedback is the point of this demo. Please open a GitHub issue at <https://github.com/MaksimKravchuk/storyteller/issues> with a title that starts with `[public demo]`.

Helpful reports include:

- the setting prompt you used;
- the turn where the problem happened;
- what you expected Storyteller to remember or do;
- what it actually did;
- screenshots or copied text if available;
- whether the issue blocked play or was just confusing, slow, inaccurate, or funny.

Especially useful feedback: places where the demo felt meaningfully different from a normal chatbot, places where it failed to respect your choices, and moments where a character or location stayed coherent across multiple turns.

## Release note

Public Web Demo v0.1 is a first public slice of Storyteller's browser-playable experience. It is intended to validate the core promise: type a premise, get an interactive story with generated places and characters, and help shape the next release with concrete feedback.
