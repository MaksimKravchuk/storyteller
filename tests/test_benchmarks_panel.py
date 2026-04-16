"""Unit tests for :mod:`benchmarks.harness.panel` — witness panel assembly."""

from __future__ import annotations

import allure
import pytest

from benchmarks.harness.panel import (
    DEFAULT_MAX_JUDGES,
    DEFAULT_ROSTER,
    _candidate_matches_override,
    _resolve_roster,
    assemble_panel,
)
from config import Config


def _cfg_with_keys(*, openai: str | None, anthropic: str | None) -> Config:
    """Build a :class:`Config` with only the api-key fields set explicitly."""
    return Config(openai_api_key=openai, anthropic_api_key=anthropic)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestPanelAssembly:
    @allure.story("Key-based filtering")
    @allure.title("assemble_panel selects every roster entry when both api keys are present")
    def test_full_panel_when_all_keys_present(self):
        assembly = assemble_panel(_cfg_with_keys(openai="sk-x", anthropic="sk-y"))

        assert len(assembly.members) == DEFAULT_MAX_JUDGES
        assert not assembly.skipped
        for member, candidate in zip(assembly.members, DEFAULT_ROSTER):
            assert member.provider == candidate.config.provider
            assert member.model_id == candidate.config.model_id

    @allure.story("Key-based filtering")
    @allure.title("assemble_panel drops anthropic candidates and records a skip reason when no anthropic key is set")
    def test_missing_anthropic_key_drops_anthropic_candidates(self):
        assembly = assemble_panel(_cfg_with_keys(openai="sk-x", anthropic=None))

        assert all(m.provider == "openai" for m in assembly.members)
        skipped_providers = {skip.provider for skip in assembly.skipped}
        assert skipped_providers == {"anthropic"}
        assert all(skip.reason == "no anthropic api key" for skip in assembly.skipped)

    @allure.story("Key-based filtering")
    @allure.title("assemble_panel drops openai candidates and records a skip reason when no openai key is set")
    def test_missing_openai_key_drops_openai_candidates(self):
        assembly = assemble_panel(_cfg_with_keys(openai=None, anthropic="sk-y"))

        assert all(m.provider == "anthropic" for m in assembly.members)
        skipped_providers = {skip.provider for skip in assembly.skipped}
        assert skipped_providers == {"openai"}

    @allure.story("Key-based filtering")
    @allure.title("assemble_panel returns an empty panel and skips every candidate when no api keys are configured")
    def test_no_keys_produces_empty_panel(self):
        assembly = assemble_panel(_cfg_with_keys(openai=None, anthropic=None))

        assert assembly.members == []
        assert len(assembly.skipped) == len(DEFAULT_ROSTER)

    @allure.story("Panel size capping")
    @allure.title("assemble_panel honours max_judges by stopping selection after the cap and flagging the remainder")
    def test_max_judges_caps_panel_and_flags_remainder(self):
        assembly = assemble_panel(
            _cfg_with_keys(openai="sk-x", anthropic="sk-y"),
            max_judges=2,
        )

        assert len(assembly.members) == 2
        reasons = {skip.reason for skip in assembly.skipped}
        assert reasons == {"panel cap reached (max_judges=2)"}
        assert len(assembly.skipped) == len(DEFAULT_ROSTER) - 2


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestPanelOverrides:
    @allure.story("Judge overrides")
    @allure.title("_candidate_matches_override matches by alias case-insensitively")
    def test_match_by_alias_case_insensitive(self):
        opus = DEFAULT_ROSTER[0]

        assert _candidate_matches_override(opus, "opus")
        assert _candidate_matches_override(opus, "OPUS")
        assert _candidate_matches_override(opus, "  Opus  ")

    @allure.story("Judge overrides")
    @allure.title("_candidate_matches_override matches by the underlying model_id case-insensitively")
    def test_match_by_model_id_case_insensitive(self):
        opus = DEFAULT_ROSTER[0]

        assert _candidate_matches_override(opus, opus.config.model_id)
        assert _candidate_matches_override(opus, opus.config.model_id.upper())

    @allure.story("Judge overrides")
    @allure.title("_resolve_roster returns the default roster when overrides are empty")
    def test_resolve_roster_default_when_no_overrides(self):
        assert _resolve_roster(None) == list(DEFAULT_ROSTER)
        assert _resolve_roster([]) == list(DEFAULT_ROSTER)

    @allure.story("Judge overrides")
    @allure.title("_resolve_roster preserves user-supplied override order and returns only the requested candidates")
    def test_resolve_roster_with_overrides_preserves_order(self):
        resolved = _resolve_roster(["gpt-5.4", "opus"])

        assert len(resolved) == 2
        assert resolved[0].alias == "gpt-5.4"
        assert resolved[1].alias == "opus"

    @allure.story("Judge overrides")
    @allure.title("_resolve_roster raises ValueError on an unknown override so typos do not silently shrink the panel")
    def test_resolve_roster_unknown_override_raises(self):
        with pytest.raises(ValueError, match="Unknown judge model"):
            _resolve_roster(["not-a-real-model"])

    @allure.story("Judge overrides")
    @allure.title("assemble_panel with overrides only returns overridden models whose providers have a key available")
    def test_overrides_still_key_filtered(self):
        assembly = assemble_panel(
            _cfg_with_keys(openai="sk-x", anthropic=None),
            overrides=["opus", "gpt-5.4"],
        )

        assert len(assembly.members) == 1
        assert assembly.members[0].model_id == "gpt-5.4"
        assert any(skip.alias == "opus" for skip in assembly.skipped)
