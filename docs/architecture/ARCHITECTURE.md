# Storyteller — Architecture

Four small diagrams, each answering one question.  Renders inline on GitHub.

---

## 1. Containers — what runs where

```mermaid
graph TB
    classDef user fill:#fff3bf,stroke:#1e1e1e
    classDef iface fill:#a5d8ff,stroke:#1e1e1e
    classDef core fill:#ffd43b,stroke:#1e1e1e
    classDef ext fill:#99e9f2,stroke:#1e1e1e

    cli["Player<br/>(local CLI)"]:::user
    tgu["Telegram User"]:::user
    webu["Web Browser"]:::user
    admu["Admin Operator"]:::user

    subgraph proc["run_server.py — one Python process"]
        bot["Telegram Bot<br/>interfaces/telegram_bot.py"]:::iface
        web["FastAPI Web UI :8070<br/>interfaces/web/app.py"]:::iface
        adm["Admin Dashboard :8080<br/>interfaces/admin.py (aiohttp)"]:::iface
        engine["GameEngine + Director cast<br/>engine/ + cast/"]:::core
    end

    main["main.py (CLI)"]:::iface

    pg[("PostgreSQL 16")]:::ext
    oai["OpenAI API"]:::ext
    anth["Anthropic API"]:::ext
    wiki["Wikipedia REST"]:::ext
    tgapi["Telegram Bot API"]:::ext

    cli --> main --> engine
    tgu --> tgapi
    bot <--> tgapi
    bot --> engine
    webu --> web --> engine
    admu --> adm
    adm -->|via GameRepository| pg

    engine --> pg
    engine --> oai
    engine --> anth
    engine --> wiki
```

---

## 2. Turn flow — what happens when the player types something

```mermaid
sequenceDiagram
    autonumber
    participant P as Player
    participant E as GameEngine
    participant D as Director
    participant T as EventManager
    participant A as Performers
    participant K as KnowledgeGraph
    participant N as Narrator
    participant DR as Dramaturge

    Note over A: Actor · SceneBuilder · NPCGenerator · ItemGenerator · WorldChronicler · Dice

    P->>E: action text
    E->>D: act(input)
    D->>D: ActionRouter classifies (TALK, MOVE, EXAMINE, ATTACK, …)
    D->>T: advance_time(cost)
    T-->>D: completed events + effects
    D->>K: query relevant facts
    D->>A: PlanExecutor delegates by verb
    A->>K: MemoryManager writes new memories
    A-->>D: turn outputs
    D->>N: render(turn outputs)
    N-->>D: prose
    opt if enabled
        D->>DR: fact-check
        DR-->>D: corrected prose
    end
    D-->>E: response
    E-->>P: narrated text
```

The Director is the only orchestrator.  Performers (`cast/`) are stateless workers; all persistent world state lives in `GameState` + `KnowledgeGraph` + `EventManager`.

---

## 3. State model — what the world looks like in memory

```mermaid
classDiagram
    direction LR

    class GameState {
        PlayerState player
        list~NPCCard~ npcs
        list~Location~ locations
        Setting setting
        WorldState world
    }
    class NPCCard {
        name, biography
        list~Goal~ goals
        list~Relationship~ relationships
    }
    class Location {
        Location parent
        list~PointOfInterest~ pois
    }
    class WorldState {
        list~WorldThread~ threads
        mood
    }
    class Setting {
        time period
        region
        key persons / events
    }
    class KnowledgeGraph {
        networkx DiGraph
        scoped queries
    }
    class KnowledgeNode {
        text
        scope: WORLD..LOCAL
        source: FACT/RUMOR/HEARSAY/PERSONAL
        canon: HISTORICAL/SESSION
    }
    class GameEvent {
        scheduled_at
        duration
        list~EventEffect~ effects
    }
    class EventManager {
        advance_time()
    }

    GameState --> NPCCard
    GameState --> Location
    GameState --> Setting
    GameState --> WorldState
    Location --> Location : parent
    KnowledgeGraph --> KnowledgeNode
    NPCCard ..> KnowledgeNode : WITNESSED
    NPCCard ..> NPCCard : TOLD_BY
    EventManager --> GameEvent
```

Knowledge edges (`WITNESSED`, `TOLD_BY`) are how rumors propagate and how each NPC knows different things.

---

## 4. Persistence path — how a turn reaches Postgres

```mermaid
graph LR
    classDef repo fill:#ced4da,stroke:#1e1e1e
    classDef io fill:#dee2e6,stroke:#1e1e1e
    classDef ext fill:#99e9f2,stroke:#1e1e1e

    engine["GameEngine"] --> repo["GameRepository<br/>db/repository.py"]:::repo

    repo --> loader["StateLoader"]:::repo
    repo --> saver["StateSaver"]:::repo
    repo --> ai["AILogStore"]:::repo
    repo --> sess["SessionStore"]:::repo
    repo --> evt["TurnEventStore"]:::repo

    loader --> conv["Converters<br/>db/converters/"]:::io
    saver --> conv
    conv --> sa["SQLAlchemy + asyncpg<br/>db/engine.py · db/tables.py"]:::io
    sa --> pg[("PostgreSQL 16<br/>JSONB tables")]:::ext

    alembic["Alembic<br/>alembic/"]:::io -. schema .-> pg
```

`GameState` and `KnowledgeGraph` are serialized into JSONB columns via the converters in `db/converters/`; relational columns are reserved for FKs and indexes.

---

## Where to look in the code

| Concern | Path |
| --- | --- |
| Public engine API | `engine/game_engine.py`, `engine/factory.py` |
| Orchestrator | `cast/director.py` |
| Performers | `cast/{actor,narrator,scene_builder,npc_generator,data_miner,item_generator,world_chronicler,dramaturge,dice}.py` |
| Performer base | `cast/base_performer_class.py` |
| Domain models | `models/` |
| Knowledge graph | `knowledge/graph.py`, `knowledge/node.py`, `knowledge/query.py`, `knowledge/memory.py` |
| Game clock | `timeline/event_manager.py`, `timeline/time_costs.py` |
| LLM layer | `llm/factory.py`, `llm/{openai,anthropic}_client.py` |
| Prompts | `prompts/base_template.py`, `prompts/*_prompts.py` |
| Persistence | `db/repository.py`, `db/converters/`, `db/tables.py` |
| Web UI | `interfaces/web/app.py`, `interfaces/web/service.py`, `engine/session_ops.py` |
| Telegram | `interfaces/telegram_bot.py` |
| Admin | `interfaces/admin.py` |
| Wikipedia | `research/wikipedia_client.py` |
