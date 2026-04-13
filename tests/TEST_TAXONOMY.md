# Test Taxonomy

Every unit test must carry four Allure decorators:

```python
@allure.epic("Combat & Action Resolution")
@allure.feature("Combat dice")
@allure.story("Outcome thresholds")
@allure.title("Player with +5 skill defends when margin is exactly 0")
def test_boundary_npc_defends_at_zero(): ...
```

- **Epic** — one of the nine product capabilities below. Required.
- **Feature** — a subsystem inside the epic (see the tables below). Required.
- **Story** — a short grouping label for related scenarios (e.g., "Outcome thresholds", "Statistical properties"). Required.
- **Title** — a full sentence describing the behavior verified, readable as spec. Required.

Prefer class-level decorators (`@allure.epic` / `@allure.feature`) so each test only needs to add `@allure.story` + `@allure.title`. Use `allure.step("…")` inside multi-phase tests to annotate arrange/act/assert blocks.

The `pytest_collection_modifyitems` hook in `tests/conftest.py` fails collection if any non-e2e test is missing one of these labels. The error message links back to this file.

---

## The nine epics

Epics reflect **what the app does for the player/operator**, not the Python package layout. This is deliberate: opening the Allure "Behaviors" tab should read like a product spec, not a package index.

| Epic | Scope |
|---|---|
| **World Setup** | Setting ingestion, DataMiner, Wikipedia research, knowledge graph population |
| **Scene & Exploration** | SceneBuilder, locations, scope-filtered knowledge, scene tracking |
| **NPC Interaction** | NPCGenerator, Actor, personality/mood, dialogue routing, NPC turns, director context formatting |
| **Combat & Action Resolution** | Dice (combat + contest), contested actions, combat routing, retaliation, physical status |
| **Narrative Delivery** | Narrator prose generation, Markdown rendering, client-specific formatting |
| **Game Timeline** | EventManager, time costs, scheduled effects, wait action, turn counting, scene transitions |
| **Memory & Persistence** | GameState fields, domain models, scene history, database engine, repository, converters |
| **Player Interfaces** | CLI, Telegram bot, admin dashboard, auth |
| **Engine & LLM Infrastructure** | GameEngine public API, BasePerformer, call chain tracking, LLM provider layer, prompt templating, config |

---

## Feature map (for current unit tests)

Find the test file you're editing in the table; use the epic/feature combo exactly as written.

### Scene & Exploration

| File | Feature | Example story |
|---|---|---|
| `test_knowledge.py` | Knowledge graph | "Scope ordering", "Query filtering", "Serialization" |
| `test_scene_tracking.py` | Scene tracking | "Conversation log scene number", "Scene converter" |

### NPC Interaction

| File | Feature | Example story |
|---|---|---|
| `test_actor_prompt.py` | Actor prompt template | "Physical status tag", "Behavioral rules" |
| `test_director_context.py` | Director context formatting | "NPC label formatting" |
| `test_director_dialogue.py` | Dialogue routing | "Duplicate NPC names", "NPC generator integration" |
| `test_director_mood.py` | Mood & status tracking | "Mood extraction", "Status updates" |
| `test_director_npc_turns.py` | NPC turn integration | "NPC turn after talk", "NPC turn after explore" |
| `test_npc_turn.py` | NPC turn resolution | "Action parsing", "Target selection" |

### Combat & Action Resolution

| File | Feature | Example story |
|---|---|---|
| `test_dice.py` | Combat dice | "Outcome categories", "Boundary conditions", "Aggression roll" |
| `test_dice_contest.py` | Contest dice | "Outcome classification", "Social contest types", "Statistics" |
| `test_contested_action.py` | Contested actions | "Combat contest", "Social contest" |
| `test_combat_status.py` | Combat status & recovery | "Status hint", "Recovery scheduling" |
| `test_director_combat.py` | Combat routing | "Dice injection", "Aggressive classification" |
| `test_director_retaliation.py` | NPC retaliation | "Retaliation on next turn", "Aggression roll integration" |

### Narrative Delivery

| File | Feature | Example story |
|---|---|---|
| `test_narrator.py` | Narrator | "Scene type selection", "Dialogue rendering" |
| `test_markdown_render.py` | Markdown rendering | "Telegram HTML", "Plain text", "HTML output" |

### Game Timeline

| File | Feature | Example story |
|---|---|---|
| `test_effect_applier.py` | Effect application | "Change status", "No-op on missing target" |
| `test_director_routing.py` | Action routing | "Turn counting", "Scene transitions", "Clarification flow" |
| `test_director_wait.py` | Wait action | "Skips dialogue", "Advances clock" |
| `test_wait_action.py` | Wait intent detection | "English keywords", "Forced wait", "Incapacitation" |
| `test_game_state_turns.py` | Turn & round tracking | "Player physical status", "Round number" |

### Memory & Persistence

| File | Feature | Example story |
|---|---|---|
| `test_models.py` | Domain models | "BaseModel UUID", "Character defaults", "NPCCard fields" |
| `test_models_game.py` | GameState model | "Initial values", "Dataclass fields", "PlayerState" |
| `test_world_state.py` | WorldState model | "Defaults", "GameState plumbing", "Round-trip", "Backwards compatibility" |
| `test_director_history.py` | Scene history & delegation | "Message pair building", "Call chain delegation" |
| `test_db_engine.py` | Database engine | "URL sslmode strip", "Engine creation" |

### Player Interfaces

| File | Feature | Example story |
|---|---|---|
| `test_cli.py` | CLI | "Game start flow", "Action input" |
| `test_admin.py` | Admin dashboard | "No-auth mode", "Session listing" |
| `test_admin_auth.py` | Admin authentication | "Token required", "Token accepted" |
| `test_telegram_wait.py` | Telegram bot | "Wait command registration" |
| `test_web_api.py` | Web UI | "Transcript building", "Current game lookup", "Start game", "Submit action", "Cookie bootstrap", "Ownership enforcement" |

### Engine & LLM Infrastructure

| File | Feature | Example story |
|---|---|---|
| `test_game_engine.py` | GameEngine public API | "State before start" |
| `test_director.py` | Director orchestration | "Private attribute encapsulation", "GameState scene fields" |
| `test_base_performer.py` | BasePerformer execution | "Agent stack tracking", "Exception safety" |
| `test_base_performer_json.py` | BasePerformer JSON send | "Successful parse", "Retry on bad JSON", "Bracket extraction" |
| `test_base_performer_logging.py` | BasePerformer logging | "Start/done records", "Error records", "JSON warnings" |
| `test_call_chain.py` | Call chain tracking | "Execute wrapper", "Parent/sequence capture" |
| `test_call_chain_logging.py` | Call chain logging | "Structured LLM log", "Parent agent in nested calls" |
| `test_call_logger.py` | Call logger context | "Buffer reset", "Agent stack context", "Sequence counter" |
| `test_openai_sanitize.py` | OpenAI client sanitization | "Control character stripping" |
| `test_config.py` | Defaults & model config | "ModelConfig dataclass", "AI_MODELS registry" |

---

## Writing a title that reads as spec

The title is the one piece that a newcomer will actually *read*. Make it a full sentence that states **what the code does**, not what the test does:

| ❌ Avoid | ✅ Prefer |
|---|---|
| `test_dice_npc_overpowers` | `Combat dice surfaces NPC_OVERPOWERS when the NPC rolls 13+ above the player` |
| `test_mood_updated` | `Actor updates NPC mood when the response contains a [MOOD:] tag` |
| `test_wait_keywords` | `Wait detection recognizes "wait", "pass", and "do nothing" as wait intents` |

Rule of thumb: if someone reads only the titles under one feature, they should understand what that feature does without looking at code.

---

## Adding a test for a new area

1. Pick the epic from the nine above (or add one in a dedicated PR if genuinely new — don't overload an existing epic).
2. Pick or add a feature entry for the subsystem under test.
3. Pick a story label that groups related scenarios.
4. Write a sentence-form title.
5. Add the file to the table in this document in the same PR.

If you're not sure which epic a new test belongs to, ask yourself: *which paragraph of the product spec would describe this behavior?* — that's the epic.
