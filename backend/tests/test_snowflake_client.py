from __future__ import annotations

import pytest

from src.config import get_settings
from src.snowflake.client import SnowflakeNotConfiguredError, get_session


def test_get_session_raises_when_unconfigured(monkeypatch):
    """execution_mode="snowflake" with no account/user/password set must
    fail loudly (never silently degrade to demo behavior) — the same
    fail-fast contract already covered implicitly for BigQuery by
    main.py's lifespan gate, tested here directly since get_session() is
    cheap to call in isolation (no FastAPI app startup needed)."""
    monkeypatch.setenv("EXECUTION_MODE", "snowflake")
    monkeypatch.delenv("SNOWFLAKE_ACCOUNT", raising=False)
    monkeypatch.delenv("SNOWFLAKE_USER", raising=False)
    monkeypatch.delenv("SNOWFLAKE_PASSWORD", raising=False)
    get_settings.cache_clear()
    get_session.cache_clear()

    try:
        with pytest.raises(SnowflakeNotConfiguredError):
            get_session()
    finally:
        get_settings.cache_clear()
        get_session.cache_clear()
