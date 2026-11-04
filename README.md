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

docker compose up -d
# Web UI: http://localhost:8070
# Admin:  http://localhost:8070/admin
```

### Local (uv)

```bash
uv sync --extra openai --extra anthropic
cp .env.example .env
# fill in your API key(s) in .env

uv run uvicorn interfaces.web.app:app --reload --host 127.0.0.1 --port 8070
```

## Configuration

Copy `.env.example` to `.env` and set your values:

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `DIRECTOR_MODEL` | `gpt-6-luna` | Model for the Director agent |
| `AGENT_MODEL` | `gpt-6-luna` | Model for supporting agents |
| `NARRATOR_MODEL` | `gpt-6-luna` | Model for the Narrator |
| `DEFAULT_PROVIDER` | `openai` | Fallback provider for unrecognised model names |
| `TEMPERATURE` | `0.7` | LLM sampling temperature |
| `MAX_TOKENS` | `2048` | Max tokens per LLM response |

Provider is auto-detected from model name: `gpt-*` → OpenAI, `claude-*` → Anthropic.

## Play

Open the web UI and start a story from the browser. The web client is the supported player interface.

## Requirements

- Python 3.11+
- An OpenAI or Anthropic API key
