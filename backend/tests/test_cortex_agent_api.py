from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_ask_returns_503_when_not_snowflake_mode(client):
    """Same gate contract as test_cortex_analyst_api.py — Cortex Agent has
    no demo equivalent either."""
    resp = client.post("/api/cortex-agent/ask", json={"question": "解約リスクの高い顧客について教えて"})

    assert resp.status_code == 503
    body = resp.json()
    assert body["detail"]["execution_mode"] == "demo"
    assert "message" in body["detail"]


def test_ask_requires_question_field(client):
    resp = client.post("/api/cortex-agent/ask", json={})
    assert resp.status_code == 422
