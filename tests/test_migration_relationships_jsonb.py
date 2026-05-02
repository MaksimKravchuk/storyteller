"""Regression: relationships migration must use a CAST that survives sa.text() parsing.

The first attempt at this migration wrote ``UPDATE npcs SET relationships = :rels::jsonb``.
SQLAlchemy's ``text()`` bind-param regex backtracks across ``::``, so it extracted the
parameter name as ``rel`` (not ``rels``). The driver then received an unbound parameter
and asyncpg raised ``syntax error at or near ":"`` — every fly.io boot tried to run the
migration and crashlooped until max-restarts.
"""

from __future__ import annotations

from importlib import util as importlib_util
from pathlib import Path

import allure
import sqlalchemy as sa

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "e1f2a3b4c5d6_promote_relationships_to_typed_model.py"
)


def _load_migration_module():
    spec = importlib_util.spec_from_file_location("_relationships_migration", _MIGRATION_PATH)
    module = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


UPDATE_NPC_RELATIONSHIPS_SQL = _load_migration_module().UPDATE_NPC_RELATIONSHIPS_SQL


@allure.epic("Memory & Persistence")
@allure.feature("Database engine")
class TestRelationshipsJsonbCast:
    @allure.story("Migration parameter binding")
    @allure.title("The relationships UPDATE binds both :rels and :id, not a backtracked :rel")
    def test_update_sql_binds_both_named_parameters(self):
        stmt = sa.text(UPDATE_NPC_RELATIONSHIPS_SQL)
        assert set(stmt._bindparams.keys()) == {"rels", "id"}

    @allure.story("Migration parameter binding")
    @allure.title("The relationships UPDATE does not contain the `:rels::jsonb` cast pattern")
    def test_update_sql_avoids_double_colon_after_bind(self):
        assert ":rels::" not in UPDATE_NPC_RELATIONSHIPS_SQL
        assert "CAST(:rels AS jsonb)" in UPDATE_NPC_RELATIONSHIPS_SQL
