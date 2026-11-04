"""Tests for research.wikipedia_client using hand-rolled async context manager fakes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import allure
import pytest

from research.wikipedia_client import WikipediaClient

pytestmark = [
    allure.epic("World Setup"),
    allure.feature("Wikipedia research"),
]

_HTTP_OK = 200
_HTTP_NOT_FOUND = 404


class _FakeResp:
    """Minimal stand-in for an ``httpx.Response`` (``status_code`` + sync ``json``)."""

    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> object:
        return self._payload


class _FakeSession:
    """Async-context-manager fake replacing ``httpx.AsyncClient``."""

    def __init__(self, resp: _FakeResp) -> None:
        self._resp = resp

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def get(self, url: str, params: object = None) -> _FakeResp:
        return self._resp


def _patch_session(resp: _FakeResp):
    session = _FakeSession(resp)
    return patch(
        "research.wikipedia_client.httpx.AsyncClient",
        MagicMock(return_value=session),
    ), session


@allure.story("Constructor")
@allure.title("WikipediaClient defaults to English Wikipedia URLs when language is not specified")
def test_default_language_urls() -> None:
    """Without a language, URLs target en.wikipedia.org."""
    client = WikipediaClient()
    assert "en.wikipedia.org" in client._rest_base
    assert "en.wikipedia.org" in client._mw_api


@allure.story("Constructor")
@allure.title("WikipediaClient swaps the subdomain to match a non-English language code")
def test_non_default_language_urls() -> None:
    """A non-default language must flow into both the REST and MW API URLs."""
    client = WikipediaClient(language="ru")
    assert client._rest_base.startswith("https://ru.wikipedia.org/")
    assert client._mw_api.startswith("https://ru.wikipedia.org/")


@allure.story("get_summary")
@allure.title("get_summary returns title, extract, and description on a 200 response")
@pytest.mark.asyncio
async def test_get_summary_returns_dict_on_200() -> None:
    """get_summary must parse the three fields from the summary JSON."""
    payload = {"title": "Rome", "extract": "Capital of Italy.", "description": "city"}
    fake_resp = _FakeResp(_HTTP_OK, payload)
    session_patch, _ = _patch_session(fake_resp)
    with session_patch:
        result = await WikipediaClient().get_summary("Rome")
    assert result == payload


@allure.story("get_summary")
@allure.title("get_summary returns a fallback dict with an 'Article not found' description on 404")
@pytest.mark.asyncio
async def test_get_summary_returns_fallback_on_404() -> None:
    """A 404 response yields the canonical fallback payload."""
    fake_resp = _FakeResp(_HTTP_NOT_FOUND, None)
    session_patch, _ = _patch_session(fake_resp)
    with session_patch:
        result = await WikipediaClient().get_summary("NoSuchPage")
    assert result == {
        "title": "NoSuchPage",
        "extract": "",
        "description": "Article not found",
    }


@allure.story("get_full_article")
@allure.title("get_full_article truncates the extracted body to the max_chars parameter")
@pytest.mark.asyncio
async def test_get_full_article_truncates_to_max_chars() -> None:
    """The returned article text must be truncated to max_chars characters."""
    long_text = "x" * 5000
    pages = {"42": {"extract": long_text}}
    fake_resp = _FakeResp(_HTTP_OK, {"query": {"pages": pages}})
    session_patch, _ = _patch_session(fake_resp)
    with session_patch:
        article = await WikipediaClient().get_full_article("Rome", max_chars=100)
    assert len(article) == 100
    assert article == "x" * 100


@allure.story("get_full_article")
@allure.title("get_full_article returns an empty string when the query returns no pages")
@pytest.mark.asyncio
async def test_get_full_article_handles_empty_pages() -> None:
    """An empty pages dict yields an empty string."""
    fake_resp = _FakeResp(_HTTP_OK, {"query": {"pages": {}}})
    session_patch, _ = _patch_session(fake_resp)
    with session_patch:
        article = await WikipediaClient().get_full_article("Rome")
    assert article == ""


@allure.story("get_full_article")
@allure.title("get_full_article returns an empty string when the MediaWiki API responds with non-200")
@pytest.mark.asyncio
async def test_get_full_article_returns_empty_on_non_200() -> None:
    """A non-200 status short-circuits and returns an empty article."""
    fake_resp = _FakeResp(500, None)
    session_patch, _ = _patch_session(fake_resp)
    with session_patch:
        article = await WikipediaClient().get_full_article("Rome")
    assert article == ""
