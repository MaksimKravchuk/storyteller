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

## Requirements

- Python 3.11+
- An OpenAI or Anthropic API key

## Deployments

Production runs on Fly.io at [storyteller-quest.fly.dev](https://storyteller-quest.fly.dev) — pushes to `main` trigger the `deploy` job in `.github/workflows/ci.yml`.

### Per-PR preview deployments

Every pull request gets its own disposable Fly.io app at `storyteller-quest-pr-<PR>.fly.dev` via `.github/workflows/fly-preview.yml`. The app is created on PR open, redeployed on every push, and destroyed when the PR is closed. Config lives in `fly.preview.toml` (machines auto-stop to keep costs near zero).

Required GitHub repository secrets:

| Secret | Purpose |
|---|---|
| `FLY_ORG_API_TOKEN` | **Org-scoped** Fly token (not the app-scoped `FLY_API_TOKEN` used for production — that one cannot create new apps). Create with `flyctl tokens create org <FLY_ORG>`. |
| `FLY_ORG` | Fly organisation slug that owns preview apps |
| `FLY_PREVIEW_DATABASE_URL` | Shared Postgres URL (`postgresql+asyncpg://...`) used by all previews |
| `OPENAI_API_KEY` | Forwarded to the preview app |
| `ANTHROPIC_API_KEY` | Forwarded to the preview app |

PRs from forks are skipped — GitHub does not expose secrets to fork workflows.
