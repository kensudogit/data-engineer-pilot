from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_ask_returns_503_when_not_snowflake_mode(client):
    """execution_mode defaults to "demo" in this test suite (see
    src/config.py) — Cortex Analyst has no demo equivalent at all, so the
    only correct response is a 503 with a structured, informative body,
    never a fabricated answer."""
    resp = client.post("/api/cortex-analyst/ask", json={"question": "チャネル別の売上を教えて"})

    assert resp.status_code == 503
    body = resp.json()
    assert body["detail"]["execution_mode"] == "demo"
    assert "message" in body["detail"]


def test_ask_requires_question_field(client):
    resp = client.post("/api/cortex-analyst/ask", json={})
    assert resp.status_code == 422  # FastAPI/pydantic validation error, before the 503 gate is even reached
