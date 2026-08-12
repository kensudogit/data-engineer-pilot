from __future__ import annotations

import math

from src.services import sales_forecast_service


def test_prepare_produces_one_series_per_channel(dataset):
    state = sales_forecast_service.prepare(dataset)
    assert set(state.channels.keys()) == {"web", "mobile_app", "marketplace"}
    for channel_metrics in state.metrics.values():
        assert math.isfinite(channel_metrics["mae"])
        assert math.isfinite(channel_metrics["rmse"])
        assert channel_metrics["mae"] >= 0


def test_forecast_returns_requested_horizon_and_is_labeled_demo(dataset):
    state = sales_forecast_service.prepare(dataset)
    resp = sales_forecast_service.forecast(state, "web", horizon_days=14)

    assert resp.source == "demo"
    assert resp.model == sales_forecast_service.MODEL_NAME
    assert resp.channel == "web"
    assert len(resp.forecast) == 14
    assert all(p.value >= 0 for p in resp.forecast)
    assert all(p.p10 is not None and p.p90 is not None and p.p10 <= p.value <= p.p90 for p in resp.forecast)


def test_forecast_unknown_channel_raises_keyerror(dataset):
    state = sales_forecast_service.prepare(dataset)
    try:
        sales_forecast_service.forecast(state, "does-not-exist")
        raise AssertionError("expected KeyError")
    except KeyError:
        pass
