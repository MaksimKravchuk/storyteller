# Storyteller

An AI-powered text quest engine with a theater-style multi-agent architecture. Describe any historical or fictional setting, and Storyteller researches it, populates a knowledge graph, and runs a cast of AI agents to narrate an immersive interactive story.

## Architecture

```
Director (GPT-4)
├── DataMiner     — researches the setting via Wikipedia
├── SceneBuilder  — constructs locations and atmosphere
├── NPCGenerator  — creates characters with backstories
├── Narrator      — writes the player-facing prose
└── MemoryManager — summarises events into the knowledge graph

KnowledgeGraph    — scoped facts (world → country → region → city)
EventManager      — timeline of world and NPC events
```

Each agent is a "performer" directed by the Director agent, which coordinates the full cast to respond to player actions.

## Quickstart

### Docker (recommended)

```bash
cp .env.example .env
# fill in your API key(s) in .env

docker build -t storyteller .
docker run -it --env-file .env storyteller
```

### Local (uv)

```bash
uv sync --extra openai --extra anthropic
cp .env.example .env
# fill in your API key(s) in .env

uv run python main.py
```

## Configuration

Copy `.env.example` to `.env` and set your values:

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `DIRECTOR_MODEL` | `gpt-5.4-mini` | Model for the Director agent |
| `AGENT_MODEL` | `gpt-5.4-nano` | Model for supporting agents |
| `NARRATOR_MODEL` | `gpt-5.4-mini` | Model for the Narrator |
| `DEFAULT_PROVIDER` | `openai` | Fallback provider for unrecognised model names |
| `TEMPERATURE` | `0.7` | LLM sampling temperature |
| `MAX_TOKENS` | `2048` | Max tokens per LLM response |

Provider is auto-detected from model name: `gpt-*` → OpenAI, `claude-*` → Anthropic.

## Example session

```
Describe your desired setting: Rome, 1st century AD, during the reign of Augustus

Researching setting and generating opening scene...

The Forum Romanum stretches before you as dawn breaks over the Palatine Hill...

> I approach the merchant stalls near the Temple of Saturn

The smell of fish sauce and fresh bread mingles in the morning air...
```

## HTTP/SSE API (for native clients)

The same engine is exposed over HTTP with SSE streaming for mobile/native clients. State lives in process memory only — there is no auth, rate limiting, or persistence; sessions vanish on restart.

```bash
uv run uvicorn interfaces.api.app:app --reload --host 127.0.0.1 --port 8071
```

Endpoints:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/sessions` | Start a new story; returns `session_id` + `opening_scene` |
| `POST` | `/sessions/{id}/actions` | Submit a player action; streams the narration as SSE |
| `GET`  | `/sessions/{id}` | Current state (scene, inventory, recent transcript) |
| `GET`  | `/sessions` | List live sessions |
| `GET`  | `/healthz` | Liveness probe |

Start a session and read the opening scene:

```bash
curl -X POST http://127.0.0.1:8071/sessions \
  -H 'content-type: application/json' \
  -d '{"setting": "Rome, 1st century AD", "language": "English"}'
```

Stream a player action (SSE `event: chunk` frames followed by a final `event: done`):

```bash
curl -N -X POST http://127.0.0.1:8071/sessions/<id>/actions \
  -H 'content-type: application/json' \
  -d '{"action": "look around"}'
```

## Requirements

- Python 3.11+
- An OpenAI or Anthropic API key
