"""Fixtures for DB-backed tests — spins a real Postgres container via testcontainers.

This module deliberately bypasses ``tests/_db_stubs.py`` so that the real
``db.engine`` / ``db.repository`` modules are loaded for every test under
``tests/db/``.  It also skips the whole module at collection time when the
Docker daemon is not reachable, keeping ``pytest tests/db/`` friction-free on
dev machines without Docker.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import uuid as _uuid
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import pytest_asyncio

_DOCKER_CHECK_TIMEOUT_SEC = 5
_STUBBED_DB_MODULES = ("db.engine", "db.repository", "db")


def _docker_available() -> bool:
    """Return True if ``docker info`` exits cleanly within the timeout."""
    try:
        docker_probe = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=_DOCKER_CHECK_TIMEOUT_SEC,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return docker_probe.returncode == 0


def _load_real_db_modules() -> tuple:
    """Pop the stubbed ``db.*`` modules and import the real ones.

    ``tests/_db_stubs.py`` injects ``MagicMock``-backed ``db.engine`` and
    ``db.repository`` entries into ``sys.modules`` via ``setdefault``.  Once
    we remove those entries, importing ``db.engine`` / ``db.repository``
    loads the real modules.
    """
    for mod_name in _STUBBED_DB_MODULES:
        sys.modules.pop(mod_name, None)
    real_engine = importlib.import_module("db.engine")
    real_repo = importlib.import_module("db.repository")
    return real_engine, real_repo


# Skip the whole package at collection time when Docker is missing.
if not _docker_available():
    pytest.skip(
        "Docker daemon not available — skipping DB-backed tests.",
        allow_module_level=True,
    )

_engine_module, _repo_module = _load_real_db_modules()

# Re-export names used by tests and fixtures within this package.
create_async_engine = _engine_module.create_async_engine
GameRepository = _repo_module.GameRepository


@asynccontextmanager
async def _rollback_conn(engine):
    """Yield an async connection wrapped in an outer transaction that always rolls back."""
    async with engine.connect() as conn:
        outer = await conn.begin()
        try:
            yield conn
        finally:
            await outer.rollback()


def _run_alembic_upgrade(database_url: str) -> None:
    """Run ``alembic upgrade head`` programmatically against the given URL."""
    alembic_command = importlib.import_module("alembic.command")
    alembic_config = importlib.import_module("alembic.config")

    project_root = Path(__file__).resolve().parents[2]
    cfg = alembic_config.Config(str(project_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(project_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    alembic_command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def postgres_url():
    """Spin a Postgres 16 container for the whole test session."""
    postgres_mod = importlib.import_module("testcontainers.postgres")
    with postgres_mod.PostgresContainer("postgres:16") as container:
        async_url = container.get_connection_url(driver="asyncpg")
        _run_alembic_upgrade(async_url)
        yield async_url


@pytest_asyncio.fixture
async def async_session(postgres_url):
    """Yield a function-scoped ``AsyncSession`` bound to a fresh engine.

    We create a new engine per test so that every test has its own event loop
    owning every connection.  asyncpg disallows reusing a connection across
    event loops, and pytest-asyncio defaults to function-scoped loops.  The
    Postgres container itself stays alive for the whole session.

    Each test runs inside an outer transaction that is rolled back on exit,
    so test bodies can freely insert / update without leaking rows.
    """
    async_session_cls = importlib.import_module("sqlalchemy.ext.asyncio").AsyncSession
    eng = create_async_engine(postgres_url)
    async with _rollback_conn(eng) as conn:
        session = async_session_cls(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            await session.close()
    await eng.dispose()


@pytest_asyncio.fixture
async def async_engine(postgres_url):
    """Expose the module-level create_async_engine helper as a fixture alias.

    Most DB tests use ``async_session`` directly; a handful of round-trip tests
    ask for an engine to trigger migration-level behaviour.  We create and
    dispose one per test for the same event-loop isolation reason as
    ``async_session``.
    """
    eng = create_async_engine(postgres_url)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def repo(async_session):
    """Return a real ``GameRepository`` bound to the savepointed session."""
    return GameRepository(async_session)


@pytest_asyncio.fixture
async def test_session_id(repo) -> str:
    """Create a fresh sessions row and return its id."""
    chat_id = _random_chat_id()
    row = await repo.sessions.create_telegram(chat_id)
    return row["id"]


_CHAT_ID_BITS = 31  # 32-bit signed positive range for telegram_chat_id
_CHAT_ID_MASK = (1 << _CHAT_ID_BITS) - 1


def _random_chat_id() -> int:
    """Return a deterministic-ish random int unique per call."""
    return int(_uuid.uuid4().int & _CHAT_ID_MASK)


# ---------------------------------------------------------------------------
# Shared populated GameState builder (used by round-trip and loader tests).
# ---------------------------------------------------------------------------


def _build_setting():
    setting_mod = importlib.import_module("models.setting")
    return setting_mod.Setting(
        name="Test Setting",
        time_period="Age of Bronze",
        region="Anatolia",
        summary="A proving ground for integration tests.",
        key_persons=[{"name": "Hero", "role": "main", "description": "Protagonist"}],
        key_events=[{"name": "Founding", "date": "-2000", "description": "City founded"}],
        locations=[{"name": "Town Square", "type": "plaza", "description": "The heart"}],
        traditions=["festival"],
        technologies=["bronze smelting"],
        social_structure="Tribal",
    )


def _build_locations():
    loc_mod = importlib.import_module("models.location")
    return [
        loc_mod.Location(
            name="Marketplace",
            description="Bustling stalls.",
            location_type="district",
            tags=["public", "busy"],
            points_of_interest=["fountain", "vendor"],
        ),
        loc_mod.Location(
            name="Tavern",
            description="Smoky common room.",
            location_type="building",
            tags=["indoor"],
        ),
    ]


def _build_npcs():
    npc_mod = importlib.import_module("models.npc_card")
    return [
        npc_mod.NPCCard(
            name="Merchant",
            biography="Travels the trade road.",
            occupation="trader",
            personality_traits=["shrewd"],
            speech_style="polite",
            attributes={"education": 4, "social_status": 5},
            inventory=["silk", "spice"],
        ),
        npc_mod.NPCCard(
            name="Guard",
            biography="Keeps the peace.",
            occupation="watchman",
            personality_traits=["stoic"],
            speech_style="curt",
            attributes={"strength": 8},
            inventory=["spear"],
        ),
        npc_mod.NPCCard(
            name="Bard",
            biography="Sings old songs.",
            occupation="entertainer",
            personality_traits=["charming"],
            speech_style="lyrical",
            attributes={"charisma": 9},
            inventory=["lyre"],
        ),
    ]


def _build_scene(location_uuid: str):
    scene_mod = importlib.import_module("models.scene")
    return scene_mod.Scene(
        location_id=location_uuid,
        description="Morning in the marketplace.",
        npcs_present=[scene_mod.SceneNPC(role="merchant")],
        points_of_interest=["fountain"],
        ambient_description="Birds sing overhead.",
        time_of_day="morning",
    )


_KG_NODE_SPECS = (
    ("Bronze is traded by weight.", "CITY", "FACT"),
    ("The king is ill.", "CITY", "RUMOR"),
    ("A caravan arrives tomorrow.", "LOCAL", "HEARSAY"),
    ("Bronze comes from tin and copper.", "WORLD", "FACT"),
    ("Something witnessed in the square.", "LOCAL", "PERSONAL_EXPERIENCE"),
)
_KG_EDGE_SPECS = (
    (0, 3, "RELATED_TO"),
    (2, 0, "TOLD_BY"),
    (4, 1, "WITNESSED"),
)


def _make_one_kg_node(node_mod, spec):
    text_val, scope_name, source_name = spec
    return node_mod.KnowledgeNode(
        text=text_val,
        scope=getattr(node_mod.KnowledgeScope, scope_name),
        source=getattr(node_mod.KnowledgeSource, source_name),
    )


def _add_kg_edges(kg, node_mod, nodes) -> None:
    for src_idx, dst_idx, edge_name in _KG_EDGE_SPECS:
        edge_type = getattr(node_mod.EdgeType, edge_name)
        kg.add_edge(nodes[src_idx].uuid, nodes[dst_idx].uuid, edge_type)


def _build_knowledge_graph():
    graph_mod = importlib.import_module("knowledge.graph")
    node_mod = importlib.import_module("knowledge.node")

    kg = graph_mod.KnowledgeGraph()
    nodes = [_make_one_kg_node(node_mod, spec) for spec in _KG_NODE_SPECS]
    for node in nodes:
        kg.add_node(node)
    _add_kg_edges(kg, node_mod, nodes)
    return kg


def _build_events():
    event_mod = importlib.import_module("timeline.event")
    return [
        event_mod.GameEvent(
            name="caravan_arrives",
            scheduled_at=float(1),
            duration=float(2),
            owner_id=None,
            location_id=None,
            scope="city",
            effects=[
                event_mod.EventEffect(
                    effect_type="ADD_ITEM",
                    target_id="player",
                    effect_data={"item": "map"},
                ),
            ],
            on_complete_description="The caravan arrives.",
        ),
        event_mod.GameEvent(
            name="tavern_brawl",
            scheduled_at=float(3),
            duration=float(1),
            owner_id=None,
            location_id=None,
            scope="local",
            on_complete_description="A brawl erupts.",
        ),
    ]


def _apply_scalars(game_state) -> None:
    game_state.turn_count = 7
    game_state.round_number = 3
    game_state.scene_number = 1
    game_state.game_clock = float(5)
    game_state.game_time = "afternoon"
    game_state.conversation_log = [{"speaker": "player", "text": "hello"}]
    game_state.scene_conversation_log = [{"speaker": "merchant", "text": "welcome"}]
    game_state.player.known_npcs = {"npc-known-1", "npc-known-2"}
    game_state.player.player_event_log = ["Entered the marketplace", "Met the merchant"]
    game_state.player.learned_facts = {"fact-bronze", "fact-king"}


def _attach_world(game_state) -> None:
    locations = _build_locations()
    for loc in locations:
        game_state.locations[loc.uuid] = loc
    for npc in _build_npcs():
        game_state.npcs[npc.uuid] = npc
    game_state.current_scene = _build_scene(locations[0].uuid)


@pytest.fixture
def populated_game_state():
    """Return a tuple ``(game_state, knowledge_graph, events)`` for round-trip tests."""
    gs_mod = importlib.import_module("models.game_state")
    kg = _build_knowledge_graph()
    game_state = gs_mod.GameState(setting=_build_setting(), knowledge_graph=kg)
    _apply_scalars(game_state)
    _attach_world(game_state)
    return game_state, kg, _build_events()
