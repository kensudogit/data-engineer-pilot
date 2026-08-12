from __future__ import annotations

from src.services import anomaly_service

# Empirically observed recall on the seed=42 dataset is ~0.29. The random
# baseline at contamination=0.015 is ~0.015 (flagging the top 1.5% by score
# would only catch injected anomalies at their base rate if scores carried
# no signal) — so 0.15 is already a ~10x-better-than-random floor, not a
# lenient target.
MIN_RECALL = 0.15


def test_prepare_detects_injected_anomalies_meaningfully_better_than_random(dataset):
    state = anomaly_service.prepare(dataset)
    assert state.metrics["recall_on_injected_anomalies"] > MIN_RECALL


def test_detect_returns_requested_limit_sorted_by_score_desc(dataset):
    state = anomaly_service.prepare(dataset)
    resp = anomaly_service.detect(state, limit=20)

    assert resp.source == "demo"
    assert resp.model == anomaly_service.MODEL_NAME
    assert len(resp.anomalies) <= 20
    scores = [a.score for a in resp.anomalies]
    assert scores == sorted(scores, reverse=True)


def test_detect_response_never_leaks_is_injected_anomaly_field(dataset):
    state = anomaly_service.prepare(dataset)
    resp = anomaly_service.detect(state, limit=20)
    for anomaly in resp.anomalies:
        assert not hasattr(anomaly, "is_injected_anomaly")


def test_detect_window_days_filters_to_recent_orders(dataset):
    from datetime import date, timedelta

    state = anomaly_service.prepare(dataset)
    resp = anomaly_service.detect(state, window_days=7, limit=1000)

    last_order_date = dataset.orders["order_date"].max()
    cutoff = last_order_date - timedelta(days=7)
    assert all(date.fromisoformat(a.order_date) >= cutoff for a in resp.anomalies)
