# ADR-0007: Gate NPC departure-line proper names at the ticker source

Date: 2026-05-30
Status: Accepted
Decision owner: Max
Related: `cast/npc_ticker.py`, `models/npc_card.py`, `cast/narrator.py`, `cast/narrator_aliases.py`, `tests/test_npc_ticker.py`, `tests/test_director_npc_ticker.py`, branch `fix/npc-ticker-departure-name-gate`, [ADR-0002 (prompt consumer-seam contract tests)](0002-prompt-consumer-seam-contract-tests.md), [ADR-0001 (feature-factory default workflow)](0001-feature-factory-default-workflow.md)

## Context

`NPCTicker` (`cast/npc_ticker.py`) is the deterministic, non-LLM resolver that evicts NPCs from the player's scene when their default daily schedule says they should not be present at the current `game_time`. For each evicted NPC it builds a human-readable departure line in `_departure_line(...)` and appends it to `TurnOutputs.npc_departures`. The Narrator then renders each of those strings verbatim — `cast/narrator.py:225` does `labels.someone_departs.format(line)` (`"Someone departs: {0}"` / `"Кто-то уходит: {0}"`) — so whatever string the ticker produces is what the player reads.

The pre-fix `_departure_line` built the label as `"Name (Occupation)"` **unconditionally**:

```python
occupation = (npc.occupation or "").strip()
label = "{0} ({1})".format(npc.name, occupation) if occupation else npc.name
```

That leaked the NPC's **proper name** even when the player had never met them. Every sibling label producer in the codebase already gates the proper name on `game_state.player.known_npcs` via `NPCCard.label_for_player` / `known_names_for_player` (`models/npc_card.py`): the Narrator's on-shift and "people visible" producers (`cast/narrator_aliases.py`) all read that gate, surfacing an unintroduced NPC as their `short_descriptor` or role fallback, never their name. The ticker was the one structured producer that bypassed it.

This is the same regression class called out in `CLAUDE.md` ("Testing") and [ADR-0002](0002-prompt-consumer-seam-contract-tests.md): a supplier emits a value the consumer (Narrator prompt body) renders, but the consumer-side wiring of the gate was never asserted.

An investigation preceded this fix and proposed a much broader remedy than a single-producer gate. **(Inferred — the proposal is not a repo artifact; reconstructed from the task brief, not from documented rationale.)** Two mechanisms were floated:

1. A broad **free-text input-scrub** that would scan arbitrary generated prose and strip not-yet-known proper names after the fact.
2. An **RU declension generator** to decline NPC names into Russian grammatical cases for natural-sounding Russian narration.

This ADR records both the fix that shipped and the deliberate decision **not** to build those two subsystems.

## Decision

**Fix the leak at the source.** `_departure_line` now takes `game_state` and routes the label through the existing gate:

```python
def _departure_line(npc, slot, game_state):
    label = npc.label_for_player(game_state, npc.occupation or "resident")
    activity = slot.activity or "steps away"
    return "{0} {1}".format(label, activity)
```

An introduced NPC (`uuid in player.known_npcs`) keeps the `"Name (Occupation)"` shape; an unintroduced NPC departs as their `short_descriptor` (or `occupation`/`"resident"` fallback). No proper name reaches `TurnOutputs.npc_departures` for an NPC the player has not met. The change is confined to `cast/npc_ticker.py` plus its tests — no prompt-template edits, no schema, no migration.

**Do not build the broad free-text input-scrub.** Departure-line text is produced by deterministic code we own, not by an LLM, so the correct place to enforce the gate is the producer, not a downstream filter over arbitrary prose.

**Do not build the RU declension generator.** The departure-line shape — a fixed `"Name (Occupation)"` parenthetical (or a descriptor) followed by one of the hardcoded activity templates, rendered after a colon in `"Кто-то уходит: {0}"` — never places the NPC name in a syntactic position that requires Russian case agreement. Declension is not needed for this rendering.

## Rationale

- **Source-gate over symptom-scrub.** The bug is that one structured producer skipped the `known_npcs` gate its siblings already honour. The minimal correct fix is to make that producer reuse the same tested `label_for_player` mechanism — three lines. A free-text scrub treats the *symptom* (a name appeared in output) and pays for it with a large, brittle subsystem: name detection over arbitrary prose is NER-grade and unreliable, it would run on every turn's output, and it can only ever approximate what the producer already knows for certain (whether `uuid in known_npcs`). Putting the gate where the identity decision is actually made is both simpler and exact.
- **Consumer-seam coverage.** Because the leaked value is a string fed straight into the Narrator's prompt body, the regression test asserts the gate on the `TurnOutputs` the Narrator actually receives — the [ADR-0002](0002-prompt-consumer-seam-contract-tests.md) consumer-seam pattern — not only inside the ticker unit.
- **No new linguistic component.** The chosen line shape sidesteps Russian declension entirely, so a declension generator would add a whole linguistic subsystem to solve a problem this rendering does not have.
- **Distinct from content safety.** The `known_npcs` gate is an identity-revelation / narrative-consistency control (the player should not read a name they have not learned in-fiction). It is a different axis from the content moderation pipeline in [ADR-0006](0006-content-safety-moderation-pipeline.md); the two should not be conflated or merged.

## Alternatives considered

### Alternative 1: Broad free-text input-scrub

A downstream pass that scans generated prose and removes proper names the player has not been introduced to. Considered because it would catch name leaks from *any* producer in one place. Rejected: name detection over arbitrary free text is unreliable (NER-grade, locale-sensitive, false-positive-prone), runs on every turn, and is strictly weaker than gating at the producer, which knows the exact `known_npcs` membership without inference. It treats the symptom rather than the missing gate. If a future *LLM-authored* surface ever emits not-yet-known names, that is a separate problem for that surface — it does not justify retrofitting a scrub over deterministic ticker output.

### Alternative 2: RU declension generator

A component to decline NPC names into Russian grammatical cases so departure (and similar) lines read naturally in Russian. Rejected on technical grounds, not effort: the departure line places the name in a fixed parenthetical after a colon (`"Кто-то уходит: Name (Occupation) …"`), an apposition that takes the nominative — no case agreement is required. Building a declension engine to serve a position that never needs it is unwarranted scope.

### Alternative 3: Leave the leak, fix it in the prompt

Tell the Narrator (via prompt instruction) to not use names for unknown NPCs. Rejected: the name is already in the input string by the time the Narrator sees it; a prompt instruction is a soft, non-deterministic guard over a value that should never have contained the name. The deterministic producer can simply not emit it.

## Consequences

Positive:
- An unintroduced NPC's proper name never reaches the player through a departure line; introduced NPCs are unaffected.
- The ticker now uses the same single identity-label mechanism as every other label producer — one place to reason about NPC name revelation.
- No new subsystem, prompt edit, schema change, or migration; the fix is contained and reversible.

Second consumer — World Chronicler (deliberate, recorded):
- `TurnOutputs.npc_departures` has **two** consumers: the Narrator (player-facing, must gate) and the World Chronicler (`cast/world_chronicler.py:65`), which is omniscient world-memory. Because `npc_departures` is a **string-only** channel, gating at `_departure_line` is the only available seam, so the Chronicler now also sees the gated descriptor (e.g. `"bartender …"`) instead of the proper name for an *unintroduced* departing NPC.
- This deviates from the dual-channel pattern the sibling fields use: `DialogueEntry` / `NPCTurnEntry` carry a separate raw `npc_name` for internal consumers (documented in `cast/schemas/turn_outputs.py`), and the Chronicler reads that raw name for dialogue/npc-turn lines (`world_chronicler.py:54,64`). Departures have no such structured name field.
- **Accepted as a minor, bounded loss.** The Chronicler concatenates the departure line into a free-text `turn_summary` prompt blob used to advance threads / schedule offscreen events / set mood (`world_chronicler.py:_summarize_turn` → `advance` prompt). It does **not** pin identity or world-state on the departure-line name in any structured or deterministic way, so the loss is reduced LLM prompt fidelity for NPCs the player has not met — and any Chronicler output that later surfaces to the player is *more* consistent for being gated, not less. The player-facing fix is correct and complete regardless.
- **Upgrade path if this ever matters:** give departures the same dual channel as dialogue/npc-turns — a structured departure entry carrying `npc_uuid` + canonical `npc_name`, gate only the player-facing render, and let the Chronicler read the raw name. Deferred here because the cost (new schema type, new consumer wiring, and the feature-factory triggers a schema/new-field change pulls in) is disproportionate to a non-identity-pinning prompt-flavor loss. Build it only against a demonstrated Chronicler need.

Tradeoffs / risks:
- The unintroduced departure line leans on `short_descriptor`; an NPC with neither a descriptor nor an occupation falls back to `"resident"`, which is intentionally generic.
- Pre-existing quirk left untouched (out of scope): the hardcoded `activity` strings are English, so they render in English inside a Russian departure line. That is a separate locale issue, not introduced or addressed here.

Deliberately deferred (reproduction-gated), not addressed here:
- **LLM-authored `npc_turns[].action` bodies.** The Actor's autonomous-action prose (`cast/npc_turn.py`, rendered at `cast/narrator.py:224`) is free text the LLM generates with `accessible_knowledge` in context, so it *could* name a not-yet-known third party. Unlike the ticker, this is not a deterministic producer skipping a known gate — it is an LLM surface, and no concrete reproduction of such a leak exists today. Per the repo's TDD discipline, the gate/scrub for this surface should be built only once a failing case is demonstrated, and justified against that surface — not pre-emptively via a broad scrub over all prose.
- **Spoken dialogue (`DialogueEntry.response`) is intentionally exempt.** An NPC *saying* a third party's name aloud is legitimate in-fiction information transfer (gossip, warnings, introductions) — the mechanism by which players learn names. Gating speech would both break that mechanic and mangle the prose. The `known_npcs` gate governs *labels and engine narration*, not what characters say.

What future agents must preserve:
- Keep NPC name revelation gated at the **producer** via `NPCCard.label_for_player` / `known_names_for_player`. Do not introduce a downstream free-text name-scrub to compensate for a producer that skipped the gate — fix the producer.
- Do not add an RU declension generator on the strength of this rendering; if a future surface genuinely needs declined names, justify it against that surface's actual syntax, not this one.
- When a new producer emits a player-facing NPC label, route it through the same gate and add a consumer-seam test asserting the gate on the value the rendering layer receives (per ADR-0002).
- Keep the `known_npcs` identity gate distinct from the ADR-0006 content-safety pipeline.

## Verification / tests

- `tests/test_npc_ticker.py` — unit-level: evicted NPCs are registered as introduced so their departure lines keep `"Name (Occupation)"`; the gate is exercised at the `_departure_line` boundary.
- `tests/test_director_npc_ticker.py::TestPlanExecutorTickerGate::test_unintroduced_departure_gated_at_narrator_seam` — **consumer-seam regression**: an NPC registered but absent from `player.known_npcs` is evicted, and the test asserts on the `TurnOutputs` the Narrator actually receives (`narrator.execute.call_args.kwargs["input_data"]`) that the proper name does **not** appear and the role **does**.
- Inspect `cast/npc_ticker.py:_departure_line` (gate present) and `models/npc_card.py:label_for_player` / `known_names_for_player` (the shared mechanism). Confirm `cast/narrator.py:225` renders `npc_departures` verbatim, so the gate must hold on the produced string.

## Related files

- `cast/npc_ticker.py`
- `models/npc_card.py`
- `cast/narrator.py`, `cast/narrator_aliases.py`, `cast/narrator_labels.py`
- `cast/world_chronicler.py` (second consumer of `npc_departures`)
- `cast/schemas/turn_outputs.py` (documents the dual-channel pattern departures lack)
- `tests/test_npc_ticker.py`
- `tests/test_director_npc_ticker.py`
