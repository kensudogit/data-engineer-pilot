from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from src.data.synth import HISTORY_DAYS, PLAN_MRR, SyntheticDataset

DEFAULT_TOP_N_PRODUCTS = 20
DEFAULT_LABEL_HORIZON_DAYS = 30
DEFAULT_SNAPSHOT_INTERVAL_DAYS = 30
DEFAULT_FEATURE_WINDOW_DAYS = 90


def daily_sales(dataset: SyntheticDataset) -> pd.DataFrame:
    """mart.daily_sales equivalent: order_date, channel, total_amount."""
    df = dataset.orders.groupby(["order_date", "channel"], as_index=False)["order_amount"].sum()
    return df.rename(columns={"order_amount": "total_amount"})


def daily_product_demand(dataset: SyntheticDataset, top_n_products: int = DEFAULT_TOP_N_PRODUCTS) -> pd.DataFrame:
    """mart.daily_product_demand equivalent, limited to the top-N products by
    revenue — matches the plan's cost-control decision (SKILL.md §6) for
    per-product ARIMA_PLUS training rather than training one series per SKU.
    """
    items = dataset.order_items.merge(dataset.orders[["order_id", "order_date"]], on="order_id")
    revenue = (items["quantity"] * items["unit_price"]).groupby(items["product_id"]).sum()
    top_products = revenue.nlargest(top_n_products).index
    items = items[items["product_id"].isin(top_products)]
    df = items.groupby(["order_date", "product_id"], as_index=False)["quantity"].sum()
    return df.rename(columns={"quantity": "quantity_sold"})


def customer_features(dataset: SyntheticDataset, snapshot_date: date) -> pd.DataFrame:
    """mart.customer_features equivalent as of snapshot_date (no forward-looking
    label). Uses only orders with order_date <= snapshot_date, so nothing here
    leaks information from after the snapshot.
    """
    customers = dataset.customers
    orders = dataset.orders[dataset.orders["order_date"] <= snapshot_date]

    window_start = snapshot_date - timedelta(days=DEFAULT_FEATURE_WINDOW_DAYS)
    recent = orders[orders["order_date"] > window_start]
    freq = recent.groupby("customer_id")["order_id"].count()
    monetary = recent.groupby("customer_id")["order_amount"].sum()
    last_order = orders.groupby("customer_id")["order_date"].max()

    rows = []
    for _, c in customers.iterrows():
        if c["signup_date"] > snapshot_date:
            continue
        # Already-churned-by-snapshot customers aren't meaningful "will they
        # churn" subjects — exclude them from the feature set entirely.
        if c["churn_date"] is not None and c["churn_date"] <= snapshot_date:
            continue

        cid = c["customer_id"]
        f = int(freq.get(cid, 0))
        m = float(monetary.get(cid, 0.0))
        last = last_order.get(cid)
        recency_days = (snapshot_date - last).days if last is not None else 9999
        rows.append(
            {
                "customer_id": cid,
                "snapshot_date": snapshot_date,
                "recency_days": recency_days,
                "frequency_90d": f,
                "monetary_90d": m,
                "avg_order_value": (m / f) if f > 0 else 0.0,
                "tenure_days": (snapshot_date - c["signup_date"]).days,
                "mrr": PLAN_MRR[c["plan_type"]],
                "plan_type": c["plan_type"],
                "region": c["region"],
            }
        )
    return pd.DataFrame(rows)


def customer_features_with_label(
    dataset: SyntheticDataset, snapshot_date: date, label_horizon_days: int = DEFAULT_LABEL_HORIZON_DAYS
) -> pd.DataFrame:
    """Adds `churned_next_30d`, computed strictly from the window
    (snapshot_date, snapshot_date + horizon] — this is a training-time-only
    helper; the live-scoring path uses customer_features() (no label).
    """
    features = customer_features(dataset, snapshot_date)
    if features.empty:
        features["churned_next_30d"] = pd.Series(dtype=bool)
        return features

    horizon_end = snapshot_date + timedelta(days=label_horizon_days)
    churn_map = dataset.customers.set_index("customer_id")["churn_date"]

    def _label(cid: str) -> bool:
        c_date = churn_map.get(cid)
        return bool(c_date is not None and snapshot_date < c_date <= horizon_end)

    features = features.copy()
    features["churned_next_30d"] = features["customer_id"].map(_label)
    return features


def customer_training_dataset(
    dataset: SyntheticDataset,
    label_horizon_days: int = DEFAULT_LABEL_HORIZON_DAYS,
    snapshot_interval_days: int = DEFAULT_SNAPSHOT_INTERVAL_DAYS,
) -> pd.DataFrame:
    """Many labeled snapshots across history, not just one as-of-today
    snapshot — gives the churn model enough rows to learn from and keeps
    each row's features/label properly separated in time (no leakage).
    """
    start = dataset.as_of_date - timedelta(days=HISTORY_DAYS)
    # Need enough history behind a snapshot for 90d features to be meaningful,
    # and enough room ahead of it for the label window to fit before "today".
    first_snapshot = start + timedelta(days=180)
    last_snapshot = dataset.as_of_date - timedelta(days=label_horizon_days)

    frames = []
    d = first_snapshot
    while d <= last_snapshot:
        frames.append(customer_features_with_label(dataset, d, label_horizon_days))
        d += timedelta(days=snapshot_interval_days)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def order_transaction_features(dataset: SyntheticDataset, window_days: int | None = None) -> pd.DataFrame:
    """mart.order_transaction_features equivalent.

    Keeps `is_injected_anomaly` in the returned frame — this is the one
    feature table where that column survives, since anomaly_service.py's
    tests need it to measure detection recall. It must never be passed as a
    model input feature, and the API schema layer must never surface it.
    """
    item_agg = dataset.order_items.groupby("order_id").agg(
        avg_unit_price=("unit_price", "mean"),
        discount_pct=("discount_pct", "mean"),
    )
    orders = dataset.orders.merge(item_agg, on="order_id", how="left")

    if window_days is not None:
        cutoff = dataset.as_of_date - timedelta(days=window_days)
        orders = orders[orders["order_date"] >= cutoff]

    orders = orders.sort_values(["customer_id", "order_date"]).reset_index(drop=True)
    order_date_ts = pd.to_datetime(orders["order_date"])
    hours_since_last = order_date_ts.groupby(orders["customer_id"]).diff().dt.total_seconds() / 3600.0
    orders["hours_since_last_order"] = hours_since_last.fillna(24 * 365)

    return orders[
        [
            "order_id",
            "order_date",
            "customer_id",
            "order_amount",
            "item_count",
            "discount_pct",
            "avg_unit_price",
            "hours_since_last_order",
            "is_injected_anomaly",
        ]
    ].rename(columns={"order_amount": "order_amount"})
