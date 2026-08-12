from __future__ import annotations

import math

from src.services import demand_forecast_service


def test_prepare_produces_at_most_top_n_products(dataset):
    state = demand_forecast_service.prepare(dataset)
    assert 1 <= len(state.products) <= 20


def test_forecast_returns_requested_horizon_and_is_labeled_demo(dataset):
    state = demand_forecast_service.prepare(dataset)
    product_id = next(iter(state.products))
    resp = demand_forecast_service.forecast(state, product_id, horizon_days=10)

    assert resp.source == "demo"
    assert resp.model == demand_forecast_service.MODEL_NAME
    assert resp.product_id == product_id
    assert len(resp.forecast) == 10
    assert all(p.value >= 0 for p in resp.forecast)


def test_list_products_matches_prepared_state(dataset):
    state = demand_forecast_service.prepare(dataset)
    options = demand_forecast_service.list_products(state)
    assert {p.product_id for p in options} == set(state.products.keys())


def test_metrics_are_finite_for_every_product(dataset):
    state = demand_forecast_service.prepare(dataset)
    for m in state.metrics.values():
        assert math.isfinite(m["mae"])
        assert math.isfinite(m["rmse"])


def test_forecast_unknown_product_raises_keyerror(dataset):
    state = demand_forecast_service.prepare(dataset)
    try:
        demand_forecast_service.forecast(state, "does-not-exist")
        raise AssertionError("expected KeyError")
    except KeyError:
        pass
