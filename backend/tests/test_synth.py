from __future__ import annotations

import pandas as pd

from src.data.synth import ANOMALY_RATE, N_CUSTOMERS, N_PRODUCTS, generate_dataset


def test_reproducibility_same_seed_gives_identical_data():
    a = generate_dataset(seed=42)
    b = generate_dataset(seed=42)

    pd.testing.assert_frame_equal(a.customers, b.customers)
    pd.testing.assert_frame_equal(a.orders, b.orders)
    pd.testing.assert_frame_equal(a.order_items, b.order_items)


def test_different_seeds_give_different_data():
    a = generate_dataset(seed=42)
    b = generate_dataset(seed=7)
    assert len(a.orders) != len(b.orders) or not a.orders["order_amount"].equals(b.orders["order_amount"])


def test_row_counts_are_in_expected_ranges(dataset):
    assert len(dataset.customers) == N_CUSTOMERS
    assert len(dataset.products) == N_PRODUCTS
    assert len(dataset.subscriptions) == N_CUSTOMERS
    assert 3000 <= len(dataset.orders) <= 15000
    assert len(dataset.order_items) > len(dataset.orders)  # most orders have 1+ items, many have several


def test_churn_signal_present(dataset):
    churned = dataset.customers["churn_date"].notna()
    # Only dormant_at_risk archetype (~15% of customers) can churn, and only
    # ~70% of those actually do — a real but modest fraction of the base.
    assert 0.02 <= churned.mean() <= 0.20


def test_anomaly_injection_rate_close_to_target(dataset):
    actual_rate = dataset.orders["is_injected_anomaly"].mean()
    # Poisson-driven daily order counts mean the realized rate won't hit
    # ANOMALY_RATE exactly — allow +/-50% relative tolerance.
    assert ANOMALY_RATE * 0.5 <= actual_rate <= ANOMALY_RATE * 1.5


def test_injected_anomalies_have_unusually_high_amounts(dataset):
    orders = dataset.orders
    normal_p95 = orders.loc[~orders["is_injected_anomaly"], "order_amount"].quantile(0.95)
    injected_median = orders.loc[orders["is_injected_anomaly"], "order_amount"].median()
    assert injected_median > normal_p95


def test_weekend_seasonality_detectable(dataset):
    orders = dataset.orders.copy()
    orders["order_date"] = pd.to_datetime(orders["order_date"])
    orders["is_weekend"] = orders["order_date"].dt.weekday >= 5

    daily_counts = orders.groupby([orders["order_date"].dt.date, "is_weekend"]).size().reset_index(name="n")
    weekend_avg = daily_counts.loc[daily_counts["is_weekend"], "n"].mean()
    weekday_avg = daily_counts.loc[~daily_counts["is_weekend"], "n"].mean()

    assert weekend_avg > weekday_avg


def test_growth_trend_present_in_daily_revenue(dataset):
    orders = dataset.orders.copy()
    orders["order_date"] = pd.to_datetime(orders["order_date"])
    daily_revenue = orders.groupby(orders["order_date"].dt.date)["order_amount"].sum().sort_index()

    first_quarter_avg = daily_revenue.iloc[: len(daily_revenue) // 4].mean()
    last_quarter_avg = daily_revenue.iloc[-len(daily_revenue) // 4 :].mean()

    assert last_quarter_avg > first_quarter_avg
