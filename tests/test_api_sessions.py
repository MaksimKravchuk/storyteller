"""Tests for the in-memory ``SessionStore``."""

from __future__ import annotations

from unittest.mock import MagicMock

import allure

from interfaces.api.sessions import SessionStore

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Mobile API"),
]


def _make_engine() -> MagicMock:
    """Return a placeholder engine — the store never calls into it."""
    return MagicMock()


@allure.story("Session store")
@allure.title("SessionStore.create assigns a unique session_id and seeds the transcript with the opening scene")
def test_create_session_seeds_transcript() -> None:
    store = SessionStore()
    entry = store.create(
        engine=_make_engine(),
        setting="Rome",
        language="English",
        opening_scene="The forum stretches before you.",
    )
    assert entry.session_id
    assert entry.transcript == [{"role": "narrator", "text": "The forum stretches before you."}]


@allure.story("Session store")
@allure.title("SessionStore.get returns None for an unknown session_id")
def test_get_unknown_session_returns_none() -> None:
    store = SessionStore()
    assert store.get("never-existed") is None


@allure.story("Session store")
@allure.title("SessionStore.list_all returns sessions ordered by created_at, oldest first")
def test_list_all_orders_by_created_at() -> None:
    store = SessionStore()
    first = store.create(engine=_make_engine(), setting="A", language="English", opening_scene="o")
    second = store.create(engine=_make_engine(), setting="B", language="English", opening_scene="o")
    assert [entry.session_id for entry in store.list_all()] == [first.session_id, second.session_id]


@allure.story("Session store")
@allure.title("Each session_id minted by SessionStore.create is unique across calls")
def test_session_ids_are_unique() -> None:
    store = SessionStore()
    ids = {
        store.create(engine=_make_engine(), setting=str(idx), language="English", opening_scene="o").session_id
        for idx in range(5)
    }
    assert len(ids) == 5
