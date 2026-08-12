from __future__ import annotations

from src.services import churn_service

# Empirically observed AUC on the seed=42 synthetic dataset is ~0.69 —
# churned_next_30d is a genuinely rare, imbalanced label (~0.7% positive
# rate per monthly snapshot), so this is a realistic bar: comfortably above
# the 0.5 no-skill baseline without demanding textbook-clean-data performance.
MIN_AUC = 0.6


def test_prepare_produces_finite_auc_above_no_skill_baseline(dataset):
    state = churn_service.prepare(dataset)
    assert state.metrics["auc"] > MIN_AUC


def test_score_returns_requested_limit_and_is_labeled_demo(dataset):
    state = churn_service.prepare(dataset)
    resp = churn_service.score(state, limit=10)

    assert resp.source == "demo"
    assert resp.model == churn_service.MODEL_NAME
    assert len(resp.customers) <= 10
    assert all(0.0 <= c.churn_probability <= 1.0 for c in resp.customers)


def test_score_is_sorted_by_descending_risk(dataset):
    state = churn_service.prepare(dataset)
    resp = churn_service.score(state, limit=50)
    probs = [c.churn_probability for c in resp.customers]
    assert probs == sorted(probs, reverse=True)


def test_risk_tier_thresholds():
    assert churn_service._risk_tier(0.9) == "high"
    assert churn_service._risk_tier(0.4) == "medium"
    assert churn_service._risk_tier(0.1) == "low"
