"""Shared E2E test fixtures."""

import pytest

from log_scrubbing import install_scrubber


@pytest.fixture(autouse=True, scope="session")
def _e2e_log_scrubber() -> None:
    """Install the shared secret scrubber for tests that hit live providers."""
    install_scrubber()
