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
| `DIRECTOR_MODEL` | `gpt-4` | Model for the Director agent |
| `AGENT_MODEL` | `gpt-3.5-turbo` | Model for supporting agents |
| `NARRATOR_MODEL` | `gpt-4` | Model for the Narrator |
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

## Requirements

- Python 3.11+
- An OpenAI or Anthropic API key
