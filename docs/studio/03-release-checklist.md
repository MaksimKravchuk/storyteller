# Storyteller Release Checklist

Use this for every release candidate.

## 1. Scope gate

- [ ] Release target named, e.g. Public Web Demo v0.1
- [ ] Must-have scope listed
- [ ] Non-goals listed
- [ ] No untriaged P0/P1 issues
- [ ] Max has approved the scope

## 2. Repository gate

- [ ] Working tree clean
- [ ] Release branch/PR exists; no direct main push by agents
- [ ] PR description includes summary and test evidence
- [ ] Version/tag decision made
- [ ] Changelog/release notes drafted

## 3. Quality gate

Run before commit/merge:

```bash
uv run ruff check . && \
uv run ruff format --check . && \
uv run flake8 . && \
uv run mypy . && \
uv run pytest tests/ --ignore=tests/e2e --ignore=tests/benchmarks
```

- [ ] Ruff lint passes
- [ ] Ruff format check passes
- [ ] Flake8/wemake passes
- [ ] Mypy passes
- [ ] Unit tests pass
- [ ] Coverage gate respected
- [ ] DB tests pass in CI

## 4. Paid/LLM quality gate

Only run with explicit cost/API-key approval:

```bash
uv run pytest tests/e2e/ --alluredir=allure-results -v
uv run python -m benchmarks run
```

- [ ] E2E tests pass or failures are triaged
- [ ] Benchmark run archived
- [ ] Narrative quality report reviewed
- [ ] Any severe coherence regressions addressed or waived

## 5. Local runtime gate

```bash
docker compose up -d
# Web UI: http://localhost:8070
# Admin:  http://localhost:8080
docker compose down
```

- [ ] Docker image builds
- [ ] Postgres healthcheck passes
- [ ] Web UI healthcheck passes
- [ ] Admin healthcheck passes
- [ ] Server logs contain no obvious startup errors

## 6. Gameplay smoke gate

For each canonical scenario:

- [ ] Start a new story
- [ ] Play 5+ turns
- [ ] Talk to an NPC
- [ ] Explore/move/inspect at least once
- [ ] Confirm memory of a recent event appears later
- [ ] Confirm no raw traceback appears in UI
- [ ] Capture notes/screenshots if something feels off

## Canonical demo scenarios

Use these scenarios for repeatable release-candidate gameplay smoke and narrative evaluation. Each scenario should be played for at least five turns so reviewers can inspect setup, agency, continuity, NPC handling, and recovery from unusual player actions.

### 1. Historical grounded: Winter market in Novgorod, 1185

Prompt:

```text
Start a grounded historical game in medieval Novgorod in the winter of 1185. I am a young scribe's apprentice sent to the market to recover a missing wax tablet before my master is blamed for a bad trade record.
```

Expected qualities:

- Establishes a plausible medieval Novgorod winter scene without modern objects, modern policing, or anachronistic social assumptions.
- Presents concrete sensory details: cold, market stalls, river trade, church bells, wax tablets, merchants, scribes, guards, or guild-like pressures.
- Gives the player actionable leads rather than a lore dump: question a merchant, inspect the stall, follow footprints, ask a guard, or visit the scribe's workspace.
- Keeps stakes human-scale and demo-friendly: reputation, debt, theft, misunderstanding, or local politics rather than world-ending danger.
- Lets NPCs have motives and imperfect knowledge; they should not all instantly trust or obey the player.

Red flags:

- Anachronisms such as phones, cameras, modern police procedure, plastic goods, or contemporary slang presented as in-world facts.
- Overconfident historical claims that feel like a textbook lecture or overwhelm the player before the first choice.
- Railroading the tablet's location without responding to the player's chosen investigative path.
- NPCs with no self-preservation, no social status concerns, or no memory of what the player just asked.
- Treating the player as a generic adventurer instead of a scribe's apprentice embedded in the setting.

5+ turn playthrough checklist:

1. Begin with the prompt and verify the opening scene names the role, missing tablet, immediate location, and at least two plausible leads.
2. Ask a market vendor about the trade record; verify the answer includes a motive, rumor, or contradiction that can be followed up.
3. Inspect the physical scene around the stall; verify sensory details and evidence are grounded in the winter market rather than generic fantasy investigation tropes.
4. Choose a social approach, such as invoking the master's name or offering to copy a receipt; verify NPC reactions reflect status and risk.
5. Follow the strongest clue to a second location; verify continuity of names, clues, time of day, and the player's prior choices.
6. Try one unexpected but plausible action, such as hiding the master's involvement or accusing the wrong merchant; verify the game handles consequences without collapsing the scenario.

### 2. Fictional/fantasy: The lantern guild of Briarfall

Prompt:

```text
Start a fantasy game in Briarfall, a forest town where enchanted lanterns keep thorn-wraiths outside the palisade. I am a newly appointed lantern-keeper on my first night shift when one district suddenly goes dark.
```

Expected qualities:

- Establishes clear fantasy rules for lanterns, thorn-wraiths, the town, and the player's duties without requiring prior lore.
- Balances wonder and threat: enchanted light, living briars, guild customs, frightened townsfolk, and a real but understandable danger.
- Provides multiple viable approaches: repair the lantern, investigate sabotage, coordinate townsfolk, seek guild records, or confront something beyond the palisade.
- Maintains consistent magic constraints; lanterns should not become unlimited problem-solvers after being introduced as fragile infrastructure.
- Lets the player shape tone through choices: cautious procedure, brave rescue, political suspicion, or occult curiosity.

Red flags:

- Generic fantasy names and exposition with no playable situation after the opening.
- Magic rules changing each turn to force a predetermined outcome.
- Thorn-wraiths acting as interchangeable combat mobs with no atmosphere, pattern, or narrative function.
- The player being overshadowed by a mentor, prophecy, or all-powerful NPC who solves the emergency.
- Forgetting the first-night-shift premise, the dark district, or prior repair/investigation decisions.

5+ turn playthrough checklist:

1. Begin with the prompt and verify the opening clearly states the dark district, immediate danger, and the lantern-keeper's available tools or responsibilities.
2. Inspect the failed lantern; verify the game offers evidence that distinguishes accident, sabotage, resource shortage, or supernatural interference.
3. Speak with a nearby resident, guild member, or watch patrol; verify the NPC adds pressure and information without solving the problem for the player.
4. Attempt a repair or containment action; verify the result follows the established lantern rules and changes the situation visibly.
5. Investigate a secondary lead, such as cut wick-silver, missing oil, thorn marks, or a suspect seen near the palisade; verify continuity with earlier evidence.
6. Make a risky choice, such as entering the dark district or delaying repair to catch a saboteur; verify consequences are tense, coherent, and recoverable for a demo session.

### 3. Weird edge-case: Bureau of Misplaced Tuesdays

Prompt:

```text
Start a surreal bureaucratic game in the Bureau of Misplaced Tuesdays. I am a temporary clerk whose desk drawer contains three copies of next Tuesday, one of which is growling and one of which has my signature on a resignation form I have never seen.
```

Expected qualities:

- Embraces the absurd premise while still giving the player a stable role, location, objective, and interaction loop.
- Keeps internal consistency for surreal rules: Tuesdays can be filed, copied, audited, misplaced, or dangerous, but the consequences should remain traceable.
- Offers clear actions despite weirdness: inspect the copies, consult a supervisor, file a form, quarantine the growling Tuesday, read the resignation, or exploit bureaucracy.
- Uses humor and strangeness without becoming random noise; each odd detail should create a choice, clue, or consequence.
- Demonstrates robust handling of edge-case player behavior and unusual nouns without refusing the premise or normalizing it into mundane office work.

Red flags:

- Rejecting the premise, explaining it away as a dream too quickly, or replacing it with a standard office mystery.
- Random surreal imagery that ignores player intent and prevents meaningful decisions.
- Losing track of which Tuesday is growling, signed, blank, copied, filed, destroyed, or carried by the player.
- Infinite escalation that makes the first five turns impossible to evaluate.
- Treating impossible actions as automatic success instead of negotiating costs, rules, and consequences.

5+ turn playthrough checklist:

1. Begin with the prompt and verify the opening preserves all three Tuesday copies, the drawer, the resignation form, and the temporary clerk role.
2. Inspect each Tuesday separately; verify the game tracks distinctions among the growling copy, signed copy, and remaining copy.
3. Try a bureaucratic action, such as filing an incident report or stamping one copy; verify forms and office rules become playable mechanics.
4. Ask an NPC supervisor or neighboring clerk for guidance; verify the NPC reacts as someone accustomed to surreal bureaucracy but not omniscient.
5. Take a risky edge-case action, such as feeding, signing, shredding, or swapping a Tuesday; verify the game responds coherently and preserves state.
6. Attempt to use the resignation-form Tuesday to change the player's future; verify consequences follow from prior choices and do not erase the scenario's tracked objects.

## Human play approval

Before public release, a human reviewer should play at least one full 5+ turn pass through each canonical scenario and record:

- whether the opening was playable without extra explanation;
- whether player choices changed subsequent turns;
- whether NPCs and world state stayed coherent;
- whether any red flags appeared;
- whether the scenario is strong enough for a public demo recording or live walkthrough.

## 7. Deployment gate

Use `docs/studio/08-fly-release-rollback.md` for the Fly.io release and rollback procedure.

- [ ] Max has approved publishing this public deploy
- [ ] Fly secrets present and current by name only; never expose values
- [ ] Deploy workflow is green or manual deploy succeeds
- [ ] Production healthcheck passes
- [ ] Demo URL opens
- [ ] Rollback path documented

## 8. Launch gate

- [ ] README quickstart accurate
- [ ] Demo URL or access instructions accurate
- [ ] Known limitations documented
- [ ] Release notes ready
- [ ] Announcement/social copy ready
- [ ] Feedback channel ready

## 9. Human approval

- [ ] Max plays release candidate
- [ ] Max approves publishing
- [ ] Release tag created
- [ ] Public announcement posted