from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture(scope="module")
def client():
    # Module-scoped: app startup trains all 5 models (a few seconds total),
    # not worth repeating per test function.
    with TestClient(app) as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["demo_mode"] is True


def test_overview(client):
    resp = client.get("/api/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "demo"
    assert len(body["summaries"]) == 5


def test_sales_forecast_default_and_explicit_channel(client):
    default_resp = client.get("/api/sales-forecast")
    assert default_resp.status_code == 200
    assert default_resp.json()["source"] == "demo"

    channels_resp = client.get("/api/sales-forecast/channels")
    assert channels_resp.status_code == 200
    channel = channels_resp.json()["channels"][0]

    explicit_resp = client.get(f"/api/sales-forecast?channel={channel}&horizon_days=7")
    assert explicit_resp.status_code == 200
    assert len(explicit_resp.json()["forecast"]) == 7


def test_sales_forecast_unknown_channel_is_404(client):
    resp = client.get("/api/sales-forecast?channel=not-a-real-channel")
    assert resp.status_code == 404


def test_churn(client):
    resp = client.get("/api/churn?limit=5")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "demo"
    assert len(body["customers"]) <= 5


def test_segmentation(client):
    resp = client.get("/api/segmentation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "demo"
    assert len(body["clusters"]) == 4


def test_anomaly(client):
    resp = client.get("/api/anomaly?limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "demo"
    assert len(body["anomalies"]) <= 10
    for anomaly in body["anomalies"]:
        assert "is_injected_anomaly" not in anomaly  # never leaked to the API layer


def test_demand_forecast_default_and_explicit_product(client):
    products_resp = client.get("/api/demand-forecast/products")
    assert products_resp.status_code == 200
    product_id = products_resp.json()["products"][0]["product_id"]

    default_resp = client.get("/api/demand-forecast")
    assert default_resp.status_code == 200

    explicit_resp = client.get(f"/api/demand-forecast?product_id={product_id}&horizon_days=5")
    assert explicit_resp.status_code == 200
    body = explicit_resp.json()
    assert body["product_id"] == product_id
    assert len(body["forecast"]) == 5


def test_demand_forecast_unknown_product_is_404(client):
    resp = client.get("/api/demand-forecast?product_id=not-a-real-product")
    assert resp.status_code == 404
